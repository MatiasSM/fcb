import os

from subprocess32 import CalledProcessError, check_output, Popen, PIPE, STDOUT

from fcb.framework.workflow.SenderTask import SenderTask, SendingError
from fcb.sending.Errors import DestinationInaccessible
from fcb.utils.log_helper import get_logger_module


class MegaAccountHandler(object):
    dir_delimiter = "/"
    dev_null = open(os.devnull, 'wb')

    @classmethod
    def to_absoulte_dst_path(cls, settings):
        dst_path = settings.dst_path
        if dst_path:
            if dst_path[-1] == MegaAccountHandler.dir_delimiter:
                dst_path = dst_path[:-1]
            root_path = "/Root"
            if not dst_path.startswith(root_path):
                dst_path = MegaAccountHandler.dir_delimiter.join((root_path, dst_path))
        return dst_path

    @classmethod
    def create_dest_directories(cls, settings):
        dst_path = cls.to_absoulte_dst_path(settings)
        log = get_logger_module(cls.__name__)
        # we generate each directory from root so we create all that are missing
        splited = dst_path.split(cls.dir_delimiter)
        subdirs = []
        # note: first 2 will be "" and root directory (since absolute path starts with "/<root>")
        for included in xrange(3, len(splited) + 1):
            subdirs.append(cls.dir_delimiter.join(splited[:included]))
        if subdirs:
            command = cls.build_command_argumetns(command_str="megamkdir", settings=settings, extra_args=subdirs)
            log.debug("Executing command: %s", command)
            cls.check_call(command)

    @classmethod
    def verify_access(cls, settings):
        log = get_logger_module(cls.__name__)
        # try megadf to check if we can access
        command = cls.build_command_argumetns(command_str="megadf", settings=settings)
        log.debug("Executing command: %s", command)

        try:
            cls.check_call(command)
        except CalledProcessError as e:
            raise DestinationInaccessible("Failed access. Running '%s' result was '%s'", command, e.output)
        log.debug("Access verified to destination mega (command: %s)", command)

    @staticmethod
    def build_command_argumetns(command_str, settings, extra_args=None):
        general_args = ["--no-ask-password", "--disable-previews"]
        return ([command_str] if settings.user is None or settings.password is None else
                [command_str, "--username", settings.user, "--password", settings.password]) \
               + general_args \
               + ([] if extra_args is None else extra_args)

    @staticmethod
    def is_output_error(output_str):
        return output_str.startswith("ERROR:")

    @staticmethod
    def check_call(command):
        process = Popen(
            command,
            stdout=PIPE,
            stderr=STDOUT,
            start_new_session=True
        )
        process_output, _ = process.communicate()
        for line in process_output.split("\n"):
            if MegaAccountHandler.is_output_error(line):
                raise CalledProcessError(1, command, process_output)


class MegaSender(SenderTask):
    def __init__(self, settings, rate_limiter=None):
        SenderTask.__init__(self)
        dst_dir_path = MegaAccountHandler.to_absoulte_dst_path(settings)
        self._base_comand = \
            MegaAccountHandler.build_command_argumetns(command_str="megaput",
                                                       settings=settings,
                                                       extra_args=["--no-progress", "--path", dst_dir_path])
        self._destination_name = settings.destinations[0]
        self._prepare_service(settings)
        self._limited_cmd = (lambda args: args) if rate_limiter is None else \
            (lambda args: rate_limiter.wrap_call(args))

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

    def destinations(self):
        return [self._destination_name]

    @staticmethod
    def _prepare_service(settings):
        MegaAccountHandler.verify_access(settings)
        MegaAccountHandler.create_dest_directories(settings)
