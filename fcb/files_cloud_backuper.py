#!/usr/bin/env python

import Queue
import signal
import sys

from fcb.database.helpers import get_session
from fcb.database.helpers import get_db_version
from fcb.database.schema import FilesDestinations
from fcb.framework.workflow.Pipeline import Pipeline
from fcb.processing.filesystem.Cleaner import Cleaner
from fcb.processing.filters.FileSizeFilter import FileSizeFilter
from fcb.processing.models.Quota import Quota
from fcb.processing.filters.QuotaFilter import QuotaFilter
from fcb.processing.filters.AlreadyProcessedFilter import AlreadyProcessedFilter
from fcb.processing.transformations.Cipher import Cipher
from fcb.processing.filesystem.Compressor import Compressor
from fcb.processing.filesystem.FileReader import FileReader
import fcb.processing.filesystem.Settings as FilesystemSettings
from fcb.processing.transformations.ToImage import ToImage
from fcb.sending.debug.FakeSender import FakeSender
from fcb.sending.SentLog import SentLog
from fcb.sending.debug.SlowSender import SlowSender
from fcb.sending.directory.ToDirectorySender import ToDirectorySender
from fcb.sending.mail.MailSender import MailSender
from fcb.sending.mega.MegaSender import MegaSender
from fcb.utils import trickle
from fcb.utils.Settings import Settings, InvalidSettings
from fcb.utils.log_helper import get_logger_module, deep_print


# noinspection PyUnresolvedReferences
import fcb.log_configuration

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
        self._pipeline.request_stop()
        log.info("Should finish processing soon")


aborter = None


def signal_handler(*_):
    global aborter

    print "Abort signal received!!!!"
    aborter.abort()


def build_pipeline(files_to_read, settings, session):
    log.debug(deep_print(settings, "Building pipeline using settings loaded:"))

    # FIXME senders setting should be simpler to handle
    sender_settings = [sender_settings for sender_settings in settings.mail_accounts]
    if settings.dir_dest is not None:
        sender_settings.append(settings.dir_dest)
    if settings.mega_settings is not None:
        sender_settings.append(settings.mega_settings)

    if not (sender_settings or settings.add_fake_sender or settings.slow_sender is not None):
        raise InvalidSettings("No senders were configured")

    fs_settings = FilesystemSettings.Settings(
        sender_settings_list=sender_settings,
        stored_files_settings=settings.stored_files)

    global_quota = Quota(
        quota_limit=settings.limits.max_shared_upload_per_day.in_bytes,
        used_quota=FilesDestinations.get_bytes_uploaded_in_date(session))

    # The pipeline goes:
    #    read files -> filter -> compress -> [cipher] -> send -> log -> finish
    pipeline = Pipeline()

    rate_limiter = None
    if settings.limits.rate_limits is not None:
        rate_limiter = trickle.TrickleBwShaper(trickle.Settings(settings.limits.rate_limits))
    files_reader = FileReader(settings.exclude_paths.path_filter_list)
    Limited_Queue = lambda: Queue.Queue(settings.performance.max_pending_for_processing)
    One_Item_Queue = lambda: Queue.Queue(1)
    pipeline \
        .add(task=files_reader.input_queue(files_to_read),
             output_queue=Limited_Queue()) \
        .add(task=FileSizeFilter(settings.limits.max_file_size.in_bytes), output_queue=One_Item_Queue()) \
        .add(task=QuotaFilter(global_quota=global_quota,
                              stop_on_remaining=settings.limits.stop_on_remaining.in_bytes,
                              request_processing_stop_cb=lambda: files_reader.request_stop()),
             output_queue=One_Item_Queue()) \
        .add(task=AlreadyProcessedFilter() if settings.stored_files.should_check_already_sent else None,
             output_queue=One_Item_Queue()) \
        .add(task=Compressor(fs_settings, global_quota), output_queue=One_Item_Queue()) \
        .add_parallel(task_builder=Cipher if settings.stored_files.should_encrypt else None,
                      output_queue=One_Item_Queue(), num_of_tasks=settings.cipher.performance.threads) \
        .add(task=ToImage() if settings.to_image.enabled else None, output_queue=One_Item_Queue()) \
        .add(task=SlowSender(settings.slow_sender) if settings.slow_sender is not None else None,
             output_queue=One_Item_Queue()) \
        .add_in_list(tasks=[MailSender(sender_conf) for sender_conf in settings.mail_accounts]
                     if settings.mail_accounts else None,
                     output_queue=One_Item_Queue()) \
        .add(task=ToDirectorySender(settings.dir_dest.path) if settings.dir_dest is not None else None,
             output_queue=One_Item_Queue()) \
        .add(task=MegaSender(settings.mega_settings, rate_limiter) if settings.mega_settings is not None else None,
             output_queue=One_Item_Queue()) \
        .add(task=FakeSender() if settings.add_fake_sender else None, output_queue=One_Item_Queue()) \
        .add(task=SentLog(settings.sent_files_log), output_queue=One_Item_Queue()) \
        .add(task=Cleaner(settings.stored_files.delete_temp_files), output_queue=None)
    return pipeline


def main():
    global aborter

    if len(sys.argv) < 3:
        log.error("Usage: %s <config_file> <input path> [<input path> ...]", sys.argv[0])
        exit(1)

    settings = Settings(sys.argv[1])

    with get_session() as session:
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

    if settings.debugging.enabled:
        from fcb.utils.debugging import configure_signals
        configure_signals()

    pipeline.start_all()
    log.debug("Waiting until processing finishes")
    while pipeline.wait_next_to_stop(timeout=1.0):
        pass
    log.debug("finished processing")

if __name__ == '__main__':
    try:
        main()
    except InvalidSettings as e:
        log.error("Failed execution: %s", e)
