#!/usr/bin/env python

import Queue
import signal
import sys

from database.helpers import get_session
from database.helpers import get_db_version
from database.schema import FilesDestinations
from framework.workflow.Pipeline import Pipeline
from processing.filesystem.Cleaner import Cleaner
from processing.models.Quota import Quota
from processing.filters.QuotaFilter import QuotaFilter
from processing.filters.AlreadyProcessedFilter import AlreadyProcessedFilter
from processing.transformations.Cipher import Cipher
from processing.filesystem.Compressor import Compressor
from processing.filesystem.FileReader import FileReader
import processing.filesystem.Settings as FilesystemSettings
from processing.transformations.ToImage import ToImage
from sending.FakeSender import FakeSender
from sending.SentLog import SentLog
from sending.directory.ToDirectorySender import ToDirectorySender
from sending.mail.MailSender import MailSender
from utils.Settings import Settings
from utils.log_helper import get_logger_module, deep_print


# noinspection PyUnresolvedReferences
import log_configuration

log = get_logger_module('main')


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


def signal_handler(*_):
    global aborter

    print "Abort signal received!!!!"
    aborter.abort()


def build_pipeline(files_to_read, settings, session):
    log.debug(deep_print(settings, "Building pipeline using settings loaded:"))

    sender_settings = [sender_settings for sender_settings in settings.mail_accounts]
    if settings.dir_dest is not None:
        sender_settings.append(settings.dir_dest)

    fs_settings = FilesystemSettings.Settings(
        sender_settings_list=sender_settings,
        stored_files_settings=settings.stored_files,
        db_session=session)

    global_quota = Quota(
        quota_limit=settings.limits.max_shared_upload_per_day.in_bytes,
        used_quota=FilesDestinations.get_bytes_uploaded_in_date(session))

    # The pipeline goes:
    #    read files -> filter -> compress -> [cipher] -> send -> log -> finish
    pipeline = Pipeline()

    Limited_Queue = lambda: Queue.Queue(settings.performance.max_pending_for_processing)
    pipeline \
        .add(task=FileReader(settings.exclude_paths.path_filter_list).input_queue(files_to_read),
             output_queue=Limited_Queue()) \
        .add(task=QuotaFilter(global_quota), output_queue=Limited_Queue()) \
        .add(task=AlreadyProcessedFilter() if settings.stored_files.should_check_already_sent else None,
             output_queue=Limited_Queue()) \
        .add(task=Compressor(fs_settings, global_quota), output_queue=Limited_Queue()) \
        .add_parallel(task_builder=Cipher if settings.stored_files.should_encrypt else None,
                      output_queue=Limited_Queue(), num_of_tasks=settings.cipher.performance.threads) \
        .add(task=ToImage() if settings.to_image.enabled else None, output_queue=Limited_Queue()) \
        .add_in_list(tasks=[MailSender(sender_conf) for sender_conf in settings.mail_accounts]
                     if settings.mail_accounts else [FakeSender()],
                     output_queue=Limited_Queue()) \
        .add(task=ToDirectorySender(settings.dir_dest.path) if settings.dir_dest is not None else None,
             output_queue=Limited_Queue()) \
        .add(task=SentLog(settings.sent_files_log), output_queue=Limited_Queue()) \
        .add(task=Cleaner(settings.stored_files.delete_temp_files), output_queue=None)
    return pipeline


if __name__ == '__main__':
    def main():
        global aborter

        if len(sys.argv) < 3:
            log.error("Usage: %s <config_file> <input path> [<input path> ...]", sys.argv[0])
            exit(1)

        settings = Settings(sys.argv[1])

        session = get_session()
        db_version = get_db_version(session)
        if db_version != 3:
            log.error("Invalid database version (%d). 3 expected" % db_version)
            session.close()
            exit(1)

        files_to_read = Queue.Queue()
        # load files to read
        for file_path in sys.argv[2:]:
            files_to_read.put(file_path)

        pipeline = build_pipeline(files_to_read, settings, session)

        session.close()

        # create gracefully finalization mechanism
        aborter = ProgramAborter(pipeline)
        signal.signal(signal.SIGINT, signal_handler)

        pipeline.start_all()
        log.debug("Waiting until processing finishes")
        while pipeline.wait_next_to_stop(timeout=1.0):
            pass
        log.debug("finished processing")

    main()
