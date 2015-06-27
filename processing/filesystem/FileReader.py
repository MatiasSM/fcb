import os

from framework.workflow.PipelineTask import PipelineTask
from processing.models.FileInfo import FileInfo


class FileReader(PipelineTask):
    # override from PipelineTask
    def process_data(self, path):
        self.log.debug("Verifying path '%s'", path)
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
            raise ValueError("The path '%s' is not a file or directory", path)
        self.log.debug("Path '%s' read", path)

        # if no more information to process, request stop
        # TODO find a better way
        if not self.has_pending_input():
            self.new_input(None)
