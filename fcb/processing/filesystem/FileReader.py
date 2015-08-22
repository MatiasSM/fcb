import os
import re

from circuits import handler

from fcb.framework import events
from fcb.framework.events import PathConsumed
from fcb.framework.workflow.PipelineTask import PipelineTask
from fcb.processing.models.FileInfo import FileInfo


class FileReader(PipelineTask):
    _path_filter_list = None
    _work_rate_controller = None

    def do_init(self, path_filter_list, work_rate_controller):
        self.log.debug("Registering path filters: %s", str(path_filter_list))
        self._path_filter_list = [re.compile(path_filter) for path_filter in path_filter_list]
        self._work_rate_controller = work_rate_controller

    @handler(events.NewInputPath.__name__)
    def new_inputh_path(self, path):
        while not self._work_rate_controller.try_acquire_slot():
            yield None  # suspend processing
        self.handle_data(path)

    # override from PipelineTask
    def process_data(self, path):
        result = None
        self.log.debug("Verifying path '%s'", path)
        if not self._matches_any_filter(path):
            if os.path.isdir(path):
                self.log.debug("Path '%s' is a directory", path)
                self.fire(PathConsumed(path))  # a directory is not processed
                for directory_entry in os.listdir(path):
                    try:
                        self.fire(events.NewInputPath(os.path.join(path, directory_entry)))
                    except ValueError:
                        pass  # don't care about entries that are not files nor directories
            elif os.path.isfile(path):
                result = FileInfo(path)
            else:
                self.log.error("The path '%s' is not a file or directory (will ignore it)", path)
                self.fire(PathConsumed(path))
            self.log.debug("Path '%s' read", path)
        else:
            self.fire(PathConsumed(path))
        return result

    def _matches_any_filter(self, path):
        for filter_rule in self._path_filter_list:
            if filter_rule.match(path) is not None:
                self.log.debug("Path '%s' matches filter '%s'", path, filter_rule.pattern)
                return True
        return False
