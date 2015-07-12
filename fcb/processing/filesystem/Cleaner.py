import os

from fcb.framework.workflow.PipelineTask import PipelineTask


class Cleaner(PipelineTask):
    def __init__(self, delete_temp_files):
        PipelineTask.__init__(self)
        self._delete_temp_files = delete_temp_files

    # override from PipelineTask
    def process_data(self, block):
        if self._delete_temp_files:
            # remove "result" files
            for tmp_file in block.all_gen_files:
                self.log.debug("REMOVING: %s", tmp_file.path)
                os.remove(tmp_file.path)
            # remove fragments
            for content_file_info in block.content_file_infos:
                if hasattr(content_file_info, 'fragment_info'):
                    os.remove(content_file_info.path)
                    self.log.debug("REMOVING: %s", content_file_info.path)
