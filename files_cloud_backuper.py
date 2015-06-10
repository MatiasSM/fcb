#!/usr/bin/env python

import Queue
import re
import signal
import sys
import xml.etree.ElementTree as Etree

from database.helpers import get_session
from database.helpers import get_db_version
from database.schema import FilesContainer
from framework.Pipeline import Pipeline
from processing.filesystem.Cleaner import Cleaner
from processing.filesystem.AlreadyProcessedFilter import AlreadyProcessedFilter
from processing.filesystem.Cipher import Cipher
from processing.filesystem.Compressor import Compressor
from processing.filesystem.FileReader import FileReader
import processing.filesystem.Settings as filesystem_settings
from sending.FakeSender import FakeSender
from sending.SentLog import SentLog
from sending.mail.MailSender import MailSender
from utils.log_helper import get_logger_module


# noinspection PyUnresolvedReferences
import log_configuration

log = get_logger_module('main')

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


# FIXME really ugly way of processing abortion
class ProgramAborter(object):
    """ Does what needs to be done when the program is intended to be graciously aborted """

    def __init__(self, pipeline):
        self._pipeline = pipeline

    def abort(self):
        log.info("Abort requested!!!!")
        self._pipeline.stop_all()
        log.info("Should finish processing soon")

aborter = None

def signal_handler(signal, frame):
    print "Abort signal received!!!!"
    aborter.abort()

def get_bytes_uploaded_today(conn):
    return FilesContainer.get_bytes_uploaded_in_date(conn)


def build_pipeline(files_to_read, conf, fs_settings, bytes_uploaded_today):
    # The pipeline goes:
    #    read files -> filter -> compress -> [cipher] -> send -> log -> finish
    pipeline = Pipeline()

    Limited_Queue = lambda: Queue.Queue(conf.max_pending_for_processing)
    pipeline \
        .add(task=FileReader().input_queue(files_to_read), output_queue=Limited_Queue())\
        .add(task=AlreadyProcessedFilter() if conf.should_check_already_sent else None, output_queue=Limited_Queue())\
        .add(task=Compressor(fs_settings, bytes_uploaded_today), output_queue=Limited_Queue())\
        .add_many(task_builder=Cipher if conf.should_encrypt_files else None,
                  output_queue=Limited_Queue(), num_of_tasks=conf.cipher_threads)\
        .add_in_list(
            tasks=[MailSender(sender_conf) for sender_conf in conf.mail_confs] if conf.mail_confs else [FakeSender()],
            output_queue=Limited_Queue())\
        .add(task=SentLog(conf.sent_files_log), output_queue=Limited_Queue())\
        .add(task=Cleaner(conf.delete_temp_files), output_queue=None)
    return pipeline


if __name__ == '__main__':
    if len(sys.argv) < 3:
        log.error("Usage: %s <config_file> <input path> [<input path> ...]", sys.argv[0])
        exit(1)

    conf = Configuration(sys.argv[1])

    session = get_session()
    db_version = get_db_version(session)
    if db_version != 3:
        log.error("Invalid database version (%d). 3 expected" % db_version)
        session.close()
        exit(1)

    bytes_uploaded_today = get_bytes_uploaded_today(session)
    log.info("According to the logs, it were already uploaded today %d bytes", bytes_uploaded_today)
    session.close()

    fs_settings = filesystem_settings.Settings()
    fs_settings.max_size_in_bytes = conf.max_size_in_bytes
    fs_settings.max_upload_per_day_in_bytes = conf.max_upload_per_day_in_bytes

    files_to_read = Queue.Queue()
    # load files to read
    for file_path in sys.argv[2:]:
        files_to_read.put(file_path)
    files_to_read.put(None)

    pipeline = build_pipeline(files_to_read, conf, fs_settings, bytes_uploaded_today)

    # create gracefully finalization mechanism
    aborter = ProgramAborter(pipeline)
    signal.signal(signal.SIGINT, signal_handler)

    pipeline.start_all()
    log.debug("Waiting until processing finishes")
    while pipeline.wait_next_to_stop(timeout=1.0):
        pass
    log.debug("finished processing")
