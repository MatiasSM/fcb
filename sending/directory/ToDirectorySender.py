import os
import shutil
from framework.workflow.PipelineTask import PipelineTask


class ToDirectorySender(PipelineTask):
    """
    Implements a sender that saves the processed files into a filesystem directory
    """
    def __init__(self, dir_path):
        PipelineTask.__init__(self)        
        self._dir_path = self._check_dir_path(dir_path)
        self.log.info("Destination directory '%s' will be used", self._dir_path)
        
    @staticmethod
    def _check_dir_path(dir_path):
        if not os.path.isdir(dir_path):
            os.makedirs(dir_path)  # we don't recheck that dir has been created (we don't support concurrent creation)
        return dir_path

    # override from PipelineTask
    def process_data(self, block):
        """
        Note: Expects Compressor Block like objects
        """
        self.log.debug("Copying file '%s'", block.ciphered_file_info.path)
        shutil.copy(block.ciphered_file_info.path, self._dir_path)
        if not hasattr(block, 'send_destinations'):  # FIXME remove, duplicated logic
            block.send_destinations = []
        block.send_destinations.append(self._dir_path)

        if not hasattr(block, 'destinations_verif_data'):  # FIXME remove, duplicated logic
            block.destinations_verif_data = {}
        block.destinations_verif_data[self._dir_path] = "Not required"

        return block
