import os
import re

from circuits import handler

from fcb.framework import events
from fcb.framework.workflow.PipelineTask import PipelineTask
from fcb.processing.models.FileInfo import FileInfo


class FileReader(PipelineTask):
    _path_filter_list = None

    def do_init(self, path_filter_list):
        self.log.debug("Registering path filters: %s", str(path_filter_list))
        self._path_filter_list = [re.compile(path_filter) for path_filter in path_filter_list]

    @handler(events.NewInputPath.__name__)
    def new_inputh_path(self, path):
        self.handle_data(path)

    # override from PipelineTask
    def process_data(self, path):
        result = None
        self.log.debug("Verifying path '%s'", path)
        if not self._matches_any_filter(path):
            if os.path.isdir(path):
                self.log.debug("Path '%s' is a directory", path)
                for directory_entry in os.listdir(path):
                    try:
                        self.fire(events.NewInputPath(os.path.join(path, directory_entry)))
                    except ValueError:
                        pass  # don't care about entries that are not files nor directories
            elif os.path.isfile(path):
                result = FileInfo(path)
            else:
                self.log.error("The path '%s' is not a file or directory (will ignore it)", path)
            self.log.debug("Path '%s' read", path)
        return result

    def _matches_any_filter(self, path):
        for filter_rule in self._path_filter_list:
            if filter_rule.match(path) is not None:
                self.log.debug("Path '%s' matches filter '%s'", path, filter_rule.pattern)
                return True
        return False
