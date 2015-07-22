import os
import re

from fcb.framework.workflow.PipelineTask import PipelineTask
from fcb.processing.models.FileInfo import FileInfo


class FileReader(PipelineTask):
    def __init__(self, path_filter_list):
        PipelineTask.__init__(self)
        self.log.debug("Registering path filters: %s", str(path_filter_list))
        self._path_filter_list = [re.compile(path_filter) for path_filter in path_filter_list]

    # override from PipelineTask
    def process_data(self, path):
        self.log.debug("Verifying path '%s'", path)
        if not self._matches_any_filter(path):
            if os.path.isdir(path):
                self.log.debug("Path '%s' is a directory", path)
                for directory_entry in os.listdir(path):
                    try:
                        self.new_input(os.path.join(path, directory_entry))
                    except ValueError:
                        pass  # don't care about entries that are not files nor directories
            elif os.path.isfile(path):
                self.new_output(FileInfo(path))
            else:
                raise ValueError("The path '{}' is not a file or directory".format(path))
            self.log.debug("Path '%s' read", path)

        # if no more information to process, request stop
        # TODO find a better way
        if not self.has_pending_input():
            self.new_input(None)

    def _matches_any_filter(self, path):
        for filter_rule in self._path_filter_list:
            if filter_rule.match(path) is not None:
                self.log.debug("Path '%s' matches filter '%s'", path, filter_rule.pattern)
                return True
        return False
