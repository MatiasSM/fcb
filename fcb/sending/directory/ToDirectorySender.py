import os
import shutil

from circuits import Worker

from fcb.framework.workflow.SenderTask import SenderTask


class ToDirectorySender(SenderTask):
    """
    Implements a sender that saves the processed files into a filesystem directory
    """
    _dir_path = None
    _worker = Worker()

    def do_init(self, dir_path):
        self._dir_path = self._check_dir_path(dir_path)
        self.log.info("Destination directory '%s' will be used", self._dir_path)

    # override from SenderTask
    def do_send(self, block):
        self.log.debug("Copying file '%s'", block.latest_file_info.path)
        shutil.copy(block.latest_file_info.path, self._dir_path)

    # override from HeavyPipelineTask
    def get_worker_channel(self):
        return self._worker

    # override from SenderTask
    def destinations(self):
        return [self._dir_path]

    # override from SenderTask
    def verification_data(self):
        return "Not required"

    @staticmethod
    def _check_dir_path(dir_path):
        if not os.path.isdir(dir_path):
            os.makedirs(dir_path)  # we don't recheck that dir has been created (we don't support concurrent creation)
        return dir_path
