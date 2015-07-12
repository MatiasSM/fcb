import os
from subprocess32 import check_call, CalledProcessError, check_output

from fcb.framework.workflow.PipelineTask import PipelineTask
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
            check_call(command, stderr=cls.dev_null, stdout=cls.dev_null, start_new_session=True)

    @classmethod
    def verify_access(cls, settings):
        log = get_logger_module(cls.__name__)
        # try megadf to check if we can access
        command = cls.build_command_argumetns(command_str="megadf", settings=settings)
        log.debug("Executing command: %s", command)
        output = check_output(command, stderr=cls.dev_null, start_new_session=True)
        if cls.is_output_error(output):
            raise DestinationInaccessible("Failed access. Running '%s' result was '%s'", command, output)
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


class MegaSender(PipelineTask):
    def __init__(self, settings):
        PipelineTask.__init__(self)
        dst_dir_path = MegaAccountHandler.to_absoulte_dst_path(settings)
        self._base_comand = \
            MegaAccountHandler.build_command_argumetns(command_str="megaput",
                                                       settings=settings,
                                                       extra_args=["--no-progress", "--path", dst_dir_path])
        self._destination_name = settings.destinations[0]
        self._prepare_service(settings)

    # override from PipelineTask
    def process_data(self, block):
        ''' FIXME currently we return block whether it was correctly processed or not because other senders are chained
            and not doing that would mean other wouldn't be able to try.'''
        if self._destination_name not in block.destinations:
            self.log.debug("Block not for this destination %s", self._destination_name)
            return block

        to_upload = block.latest_file_info.path
        self.log.info("Starting upload of '%s'", to_upload)
        command = self._base_comand + [to_upload]
        self.log.debug("Executing: %s", command)
        try:
            check_call(args=command, start_new_session=True)

            if not hasattr(block, 'send_destinations'):  # FIXME remove, duplicated logic
                block.send_destinations = []
            block.send_destinations.append(self._destination_name)
        except CalledProcessError as e:
            self.log.error("Upload of '%s' failed: %s", to_upload, e)

        return block

    @staticmethod
    def _prepare_service(settings):
        MegaAccountHandler.verify_access(settings)
        MegaAccountHandler.create_dest_directories(settings)
