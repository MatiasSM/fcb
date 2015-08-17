from fcb.framework.workflow.PipelineTask import PipelineTask


class FileSizeFilter(PipelineTask):
    _file_size_limit_bytes = None

    def do_init(self, file_size_limit_bytes):
        self._file_size_limit_bytes = file_size_limit_bytes

    # override from PipelineTask
    def process_data(self, file_info):
        """expects FileInfo"""
        if self._exceeds_max_file_size(file_info):
            self.log.info("File '%s' has a size in bytes (%d) greater than the configured limit. Will be ignored.",
                          file_info.path, file_info.size)
            return None
        else:
            return file_info

    def _exceeds_max_file_size(self, file_info):
        return self._file_size_limit_bytes != 0 and file_info.size > self._file_size_limit_bytes
