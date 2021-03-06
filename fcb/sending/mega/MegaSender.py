from subprocess32 import CalledProcessError

from fcb.framework.workers import mega_sender_worker_pool
from fcb.framework.workflow.SenderTask import SenderTask, SendingError
from fcb.sending.mega.helpers import MegaAccountHandler

_worker_pool = mega_sender_worker_pool


class MegaSender(SenderTask):
    _base_comand = None
    _destination_name = None
    _limited_cmd = None

    def do_init(self, settings, rate_limiter=None):
        super(MegaSender, self).do_init()
        dst_dir_path = MegaAccountHandler.to_absoulte_dst_path(settings)
        self._base_comand = \
            MegaAccountHandler.build_command_argumetns(command_str="megaput",
                                                       settings=settings,
                                                       extra_args=["--no-progress", "--path", dst_dir_path])
        self._destination_name = settings.destinations[0]
        self._prepare_service(settings)
        self._limited_cmd = (lambda args: args) if rate_limiter is None else \
            (lambda args: rate_limiter.wrap_call(args))

    # override from SenderTask
    def do_send(self, block):
        to_upload = block.latest_file_info.path
        self.log.info("Starting upload of '%s'", to_upload)
        command = self._limited_cmd(self._base_comand + [to_upload])
        self.log.debug("Executing: %s", command)
        try:
            MegaAccountHandler.check_call(command)
        except CalledProcessError as e:
            self.log.error("Upload of '%s' failed: %s", to_upload, e)
            raise SendingError(e)

    # override from HeavyPipelineTask
    def get_worker_channel(self):
        return _worker_pool.get_worker()

    # override from SenderTask
    def destinations(self):
        return [self._destination_name]

    @staticmethod
    def _prepare_service(settings):
        if settings.verify_access:
            MegaAccountHandler.verify_access(settings)
        MegaAccountHandler.create_dest_directories(settings)
