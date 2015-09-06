#!/usr/bin/env python

import signal
import sys

from circuits import Component, Debugger, BaseComponent
from circuits.core.handlers import handler

from fcb.database.helpers import get_session
from fcb.database.helpers import get_db_version
from fcb.database.schema import FilesDestinations
from fcb.framework import events, workers
from fcb.framework.Marker import MarkerTask, Marks
from fcb.framework.events import FlushPendings, NewInputPath
from fcb.framework.workflow.Pipeline import Pipeline
from fcb.framework.workflow.WorkRate import WorkRateController
from fcb.processing.filesystem.Cleaner import Cleaner
from fcb.processing.filters.FileSizeFilter import FileSizeFilter
from fcb.processing.filters.PathFilter import PathFilter
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


class App(Component):
    pipeline = Pipeline()

    def init(self, settings, session):
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
        rate_limiter = None
        if settings.limits.rate_limits is not None:
            rate_limiter = trickle.TrickleBwShaper(trickle.Settings(settings.limits.rate_limits))

        work_rate_controller = \
            WorkRateController(max_pending_for_processing=settings.performance.max_pending_for_processing)
        work_rate_controller.register(self)
        files_reader = \
            FileReader(path_filter_list=settings.exclude_paths.path_filter_list,
                       work_rate_controller=work_rate_controller)

        if settings.performance.filter_by_path:
            PathFilter().register(self)

        self.pipeline \
            .add(files_reader, disable_on_shutdown=True) \
            .add(FileSizeFilter(file_size_limit_bytes=settings.limits.max_file_size.in_bytes),
                 disable_on_shutdown=True) \
            .add(QuotaFilter(global_quota=global_quota, stop_on_remaining=settings.limits.stop_on_remaining.in_bytes),
                 disable_on_shutdown=True) \
            .add(AlreadyProcessedFilter() if settings.stored_files.should_check_already_sent else None,
                 disable_on_shutdown=True) \
            .add(Compressor(fs_settings=fs_settings, global_quota=global_quota), disable_on_shutdown=True) \
            .add(Cipher() if settings.stored_files.should_encrypt else None, disable_on_shutdown=True) \
            .add(ToImage() if settings.to_image.enabled else None, disable_on_shutdown=True) \
            .add(MarkerTask(mark=Marks.sending_stage), disable_on_shutdown=True) \
            .add(SlowSender(settings=settings.slow_sender) if settings.slow_sender is not None else None,
                 disable_on_shutdown=True) \
            .add_in_list([MailSender(mail_conf=sender_conf) for sender_conf in settings.mail_accounts]
                         if settings.mail_accounts else None) \
            .add(ToDirectorySender(dir_path=settings.dir_dest.path) if settings.dir_dest is not None else None) \
            .add(MegaSender(settings=settings.mega_settings, rate_limiter=rate_limiter)
                 if settings.mega_settings is not None else None) \
            .add(FakeSender() if settings.add_fake_sender else None) \
            .add(SentLog(sent_log=settings.sent_files_log)) \
            .add(Cleaner(delete_temp_files=settings.stored_files.delete_temp_files)) \
            .add(MarkerTask(mark=Marks.end_of_pipeline))


class PipelineFlusher(BaseComponent):
    _remaining_inputs = 0

    @handler(NewInputPath.__name__)
    def _on_new_input_path(self, *_):
        self._remaining_inputs += 1

    @handler(NewInputPath.__name__ + "_complete")
    def _on_input_path_processed(self, *_):
        self._notify_completed()

    def _notify_completed(self):
        self._remaining_inputs -= 1
        if self._remaining_inputs == 0:
            self.fire(FlushPendings())


def main():
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

        app = App(settings, session)

        workers.manager.register_app(app)

        in_files = sys.argv[2:]
        PipelineFlusher(remaining_inputs=len(in_files)).register(app)

        # load files to read
        for file_path in in_files:
            event = events.NewInputPath(file_path)
            event.complete = True
            app.fire(event)

        session.close()

    if settings.debugging.enabled:
        from fcb.utils.debugging import configure_signals
        configure_signals()

        app += Debugger()

    app.run()
    log.debug("finished processing")


if __name__ == '__main__':
    try:
        main()
    except InvalidSettings as e:
        log.error("Failed execution: %s", e)
