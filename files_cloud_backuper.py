#!/usr/bin/env python

import Queue
import os
import re
import signal
import sys
import xml.etree.ElementTree as Etree

from database.helpers import create_connection
from database.helpers import get_db_version
from database.schema import FilesContainer
from processing.filesystem.AlreadyProcessedFilter import AlreadyProcessedFilter
from processing.filesystem.Cipher import Cipher
from processing.filesystem.Compressor import Compressor
from processing.filesystem.File_Reader import File_Reader
import processing.filesystem.Settings as filesystem_settings
from sending.FakeSender import FakeSender
from sending.Queuer import Queuer
from sending.SentLog import SentLog
from sending.mail.MailSender import MailSender
from utils.Task import Task
from utils.log_helper import get_logger_module

# noinspection PyUnresolvedReferences
import log_configuration

log = get_logger_module('main')

###### HELPER CLASSES ######   

# FIXME not pythonic nor flexible enough
class Configuration(object):
    class Size(object):
        parse_regex = re.compile('^ *([0-9]{1,}) *([kK]|[mM]|[gG]| *) *$')
        unit_factor = {'g': 1000 ** 3, 'm': 1000 ** 2, 'k': 1000, '': 1}

        def __init__(self, size_str):
            result = self.parse_regex.match(size_str)
            if result is not None:
                self.in_bytes = int(result.group(1)) * self.unit_factor[result.group(2).strip().lower()]
                log.debug("String '%s' parsed as '%d' bytes", size_str, self.in_bytes)
            else:
                raise RuntimeError("'%s' is not a valid size string" % size_str)

    class MailConf(object):
        def __init__(self, root):
            """ Should receive as "root" the <account> """
            self.dst_mail = []
            self.subject_prefix = ''
            self.retries = 3
            self.time_between_retries = 1
            for child in root:
                if child.tag == "src":
                    self.src_mail = child.find('mail').text
                    self.src_user = child.find('user').text
                    self.src_password = child.find('pass').text
                    self.mail_server = child.find('server').text
                    self.use_ssl = True
                    use_ssl = child.find('use_ssl')
                    if use_ssl is not None:
                        self.use_ssl = False if use_ssl.text == "0" else True
                    self.mail_server_port = 465 if self.use_ssl else 25
                    port = child.find('server_port')
                    if port is not None:
                        self.mail_server_port = int(port.text)
                elif child.tag == "dst_mail":
                    self.dst_mail.append(child.text)
                elif child.tag == "subject_prefix":
                    self.subject_prefix = child.text if child.text else ''
                elif child.tag == "retries":
                    self.retries = int(child.text)
                elif child.tag == "time_between_retries":
                    self.time_between_retries = int(child.text)
                else:
                    log.warning("In Mail configuration, tag '%s' not recognized. Will be ignored.", child.tag)

    def __init__(self, file_path):
        self.cipher_threads = 1
        self.sender_threads = 1
        self.max_upload_per_day_in_bytes = 0
        self.max_size_in_bytes = 5000000
        self.should_encrypt_files = False
        self.mail_confs = []

        self._parse(Etree.parse(file_path))

    def _parse(self, tree):
        for child in tree.getroot():
            if child.tag == "performance":
                self.cipher_threads = int(child.find('cipher_threads').text)
                self.sender_threads = int(child.find('sender_threads').text)
                self.max_pending_for_processing = int(child.find('max_pending_for_processing').text)
            elif child.tag == "stored_files":
                self.max_upload_per_day_in_bytes = self.Size(child.find('max_upload_per_day').text).in_bytes
                self.max_size_in_bytes = self.Size(child.find('max_size').text).in_bytes
                self.should_encrypt_files = False if child.find('should_encrypt').text == "0" else True
                self.should_check_already_sent = False if child.find('should_check_already_sent').text == "0" else True
                self.delete_temp_files = False if child.find('delete_temp_files').text == "0" else True
            elif child.tag == "mail_sender":
                for account in child.iter('account'):
                    self.mail_confs.append(self.MailConf(account))
            elif child.tag == "sent_files_log":
                self.sent_files_log = child.text
            else:
                log.warning("Tag '%s' not recognized. Will be ignored.", child.tag)


###### PIPE LINE FUNCTIONS ######

def read_files(reader, files):
    for path in files:
        log.info("Reading: %s", path)
        reader.read(path)
    log.debug("Finished reading files")


def process_data(processor_function, finalization_function, in_queue):
    try:
        while True:
            data = in_queue.get()
            if data:
                processor_function(data)
            else:
                log.debug("Finished processing data")
                break
        if finalization_function:
            finalization_function()
    except Exception, e:
        log.error("Unhandled exception while processing: %s", str(e), exc_info=1)


def multi_process_data(processor_functions, finalization_functions, in_queue):
    try:
        while True:
            data = in_queue.get()
            if data:
                for processor_function in processor_functions:
                    result = processor_function(data)
                    if result is not None and not result:
                        # TODO HACER CONFIGURABLE QUE HACER CON ESTO
                        log.error("Failed to process information. Skipping multi process of data")
                        break
            else:
                log.debug("Finished processing data")
                break
        for finalization_function in finalization_functions:
            finalization_function()
    except Exception, e:
        log.error("Unhandled exception while processing: %s", str(e), exc_info=1)


def finish_processing(in_queue, delete_temp_files):
    while True:
        block = in_queue.get()
        if block:
            if delete_temp_files:
                log.debug("REMOVE: %s" % block.processed_data_file_info.path)
                os.remove(block.processed_data_file_info.path)
                if hasattr(block, 'ciphered_file_info'):
                    os.remove(block.ciphered_file_info.path)
                    log.debug("REMOVE: %s" % block.ciphered_file_info.path)
                for content_file_info in block.content_file_infos:
                    if hasattr(content_file_info, 'fragment_info'):
                        os.remove(content_file_info.path)
                        log.debug("REMOVE: %s" % content_file_info.path)
            log.info("Sent file %s containing files: %s" %
                     (block.processed_data_file_info.basename,
                      str([file_info.path for file_info in block.content_file_infos])))
        else:
            log.debug("Finish post-processing files")
            break


def create_processing_task(threads_count,
                           processing_object, processing_method_name, processing_finish_method_name,
                           input_queue, task_name=None):
    process_data_arguments = \
        {'processor_function': getattr(processing_object, processing_method_name),
         'finalization_function': getattr(processing_object, processing_finish_method_name) \
             if processing_finish_method_name else None,
         'in_queue': input_queue}
    return Task(threads_count=threads_count,
                activity=process_data,
                activity_args=process_data_arguments,
                activity_stop=getattr(input_queue, 'put'),
                activity_stop_args=(None,),
                name=':'.join((processing_object.__class__.__name__, processing_method_name)))


def create_multiprocessing_task(threads_count,
                                processing_objects, processing_method_name, processing_finish_method_name,
                                input_queue):
    ''' 
    Creates a Task which will execute a "multi_process_data" associated to the methods of the "processing_objects"
    '''

    multi_process_data_arguments = \
        {'processor_functions': [getattr(proc_obj, processing_method_name) for proc_obj in processing_objects],
         'finalization_functions': [getattr(proc_o, processing_finish_method_name) for proc_o in processing_objects] \
             if processing_finish_method_name else None,
         'in_queue': input_queue}
    return Task(threads_count=threads_count,
                activity=multi_process_data,
                activity_args=multi_process_data_arguments,
                activity_stop=getattr(input_queue, 'put'),
                activity_stop_args=(None,))


# FIXME really ugly way of processing abortion
class Program_Aborter(object):
    ''' Does what needs to be done when the program is intended to be graciously aborted
        Currently it means clearing the pipeline so no more jobs are to be programmed '''

    def __init__(self, queues_to_clear, reader, tasks_to_stop):
        self._queues_to_clear = queues_to_clear
        self._reader = reader
        self._task_to_stop = tasks_to_stop

    def abort(self):
        log.info("Abort requested!!!!")
        self._reader.stop()
        self._clear_queues()
        # need to clear twice because the first will unlock the reading thread and let the pending read to complete
        self._clear_queues()
        for task in self._task_to_stop:
            task.request_stop()
        log.info("Should finish processing soon")

    def _clear_queues(self):
        log.debug("Clearing queues")
        for queue in self._queues_to_clear:
            try:
                while True:
                    queue.get_nowait()
            except Queue.Empty:
                pass

            ##################


aborter = None


def signal_handler(signal, frame):
    print "Abort signal received!!!!"
    aborter.abort()


def wait_task_to_stop(task):
    while task.is_alive():
        task.wait(timeout=1.0)


def get_bytes_uploaded_today(conn):
    return FilesContainer.get_bytes_uploaded_in_date(conn)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        log.error("Usage: %s <config_file> <input path> [<input path> ...]", sys.argv[0])
        exit(1)

    conf = Configuration(sys.argv[1])

    # The pipe line goes:
    #    read files -> filter -> compress -> [cipher] -> send -> log -> finish

    files_to_read = Queue.Queue()
    files_read = Queue.Queue(conf.max_pending_for_processing)
    files_filtered = files_read  # by default there is no filter
    files_compressed = Queue.Queue(conf.max_pending_for_processing)
    files_encrypted = files_compressed  # by default there is no encryption
    files_sent = Queue.Queue(conf.max_pending_for_processing)
    files_logged = Queue.Queue(conf.max_pending_for_processing)

    conn = create_connection()
    db_version = get_db_version(conn)
    if db_version != 3:
        log.error("Invalid database version (%d). 3 expected" % db_version)
        conn.close()
        exit(1)

    fs_settings = filesystem_settings.Settings()
    fs_settings.max_size_in_bytes = conf.max_size_in_bytes
    fs_settings.max_upload_per_day_in_bytes = conf.max_upload_per_day_in_bytes

    bytes_uploaded_today = get_bytes_uploaded_today(conn)
    log.info("According to the logs, it were already uploaded today %d bytes", bytes_uploaded_today)
    reader = File_Reader(files_read)
    ap_filter = None
    if conf.should_check_already_sent:
        files_filtered = Queue.Queue(conf.max_pending_for_processing)
        ap_filter = AlreadyProcessedFilter(files_filtered)
    compressor = Compressor(fs_settings, files_compressed, bytes_uploaded_today)
    cipher = None
    if conf.should_encrypt_files:
        files_encrypted = Queue.Queue(conf.max_pending_for_processing)
        cipher = Cipher(files_encrypted)
    senders = []
    if conf.mail_confs:
        for sender_conf in conf.mail_confs:
            senders.append(MailSender(sender_conf))
    else:
        senders.append(FakeSender())
    senders.append(Queuer(files_sent))
    sent_log = SentLog(conf.sent_files_log, files_logged)

    conn.close()

    # load files to read
    for file_path in sys.argv[2:]:
        files_to_read.put(file_path)
    files_to_read.put(None)

    # Create tasks
    reader_task = create_processing_task(threads_count=1,
                                         processing_object=reader, processing_method_name='read',
                                         processing_finish_method_name='stop',
                                         input_queue=files_to_read)
    tasks = []
    if ap_filter:
        tasks.append(create_processing_task(threads_count=1,
                                            processing_object=ap_filter, processing_method_name='filter',
                                            processing_finish_method_name='finish',
                                            input_queue=files_read))
    tasks.append(create_processing_task(threads_count=1,
                                        processing_object=compressor, processing_method_name='process_file',
                                        processing_finish_method_name='flush',
                                        input_queue=files_filtered))
    if cipher:
        tasks.append(create_processing_task(threads_count=conf.cipher_threads,
                                            processing_object=cipher, processing_method_name='encrypt',
                                            processing_finish_method_name=None,
                                            input_queue=files_compressed))
    tasks.append(create_multiprocessing_task(threads_count=conf.sender_threads,
                                             processing_objects=senders, processing_method_name='send',
                                             processing_finish_method_name='close',
                                             input_queue=files_encrypted))
    tasks.append(create_processing_task(threads_count=1,
                                        processing_object=sent_log, processing_method_name='log',
                                        processing_finish_method_name='close',
                                        input_queue=files_sent))
    tasks.append(Task(threads_count=1, activity=finish_processing,
                      activity_args=(files_logged, conf.delete_temp_files),
                      activity_stop=getattr(files_logged, 'put'), activity_stop_args=(None,), name="Finish"))

    # create gracefully finalization mechanism
    tasks_to_abort = [reader_task]
    tasks_to_abort.extend(tasks[:-1])
    aborter = Program_Aborter(
        queues_to_clear=[files_to_read, files_read, files_filtered, files_compressed, files_encrypted],
        reader=reader,
        tasks_to_stop=tasks_to_abort)
    signal.signal(signal.SIGINT, signal_handler)

    # start tasks
    reader_task.start()
    for task in tasks:
        task.start()

    log.debug("Waiting until processing finishes")

    wait_task_to_stop(reader_task)  # the reader tasks shouldn't be stopped
    for task in tasks:
        # stop one by one the task, note that because they are in the pipe line order, all the processing will be
        # finished by the time they stop
        task.request_stop()
        wait_task_to_stop(task)

    log.debug("finished processing")
