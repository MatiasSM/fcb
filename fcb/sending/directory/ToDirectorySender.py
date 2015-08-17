import os
import shutil

from fcb.framework.workers import hd_worker_pool
from fcb.framework.workflow.SenderTask import SenderTask

_worker_pool = hd_worker_pool


class ToDirectorySender(SenderTask):
    """
    Implements a sender that saves the processed files into a filesystem directory
    """
    _dir_path = None

    def do_init(self, dir_path):
        super(ToDirectorySender, self).do_init()
        self._dir_path = self._check_dir_path(dir_path)
        self.log.info("Destination directory '%s' will be used", self._dir_path)

    # override from SenderTask
    def do_send(self, block):
        self.log.debug("Copying file '%s'", block.latest_file_info.path)
        shutil.copy(block.latest_file_info.path, self._dir_path)

    # override from HeavyPipelineTask
    def get_worker_channel(self):
        return _worker_pool.get_worker()

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
