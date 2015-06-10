import os
from framework.PipelineTask import PipelineTask


class Cleaner(PipelineTask):
    def __init__(self, delete_temp_files):
        PipelineTask.__init__(self)
        self._delete_temp_files = delete_temp_files

    # override from PipelineTask
    def process_data(self, block):
        if self._delete_temp_files:
            self.log.debug("REMOVE: %s", block.processed_data_file_info.path)
            os.remove(block.processed_data_file_info.path)
            if hasattr(block, 'ciphered_file_info'):
                os.remove(block.ciphered_file_info.path)
                self.log.debug("REMOVE: %s", block.ciphered_file_info.path)
            for content_file_info in block.content_file_infos:
                if hasattr(content_file_info, 'fragment_info'):
                    os.remove(content_file_info.path)
                    self.log.debug("REMOVE: %s", content_file_info.path)
        self.log.info("Sent file %s containing files: %s",
                      block.processed_data_file_info.basename,
                      str([file_info.path for file_info in block.content_file_infos]))
