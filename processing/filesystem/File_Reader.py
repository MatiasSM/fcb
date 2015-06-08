import os
from processing.filesystem.File_Info import File_Info
from utils.log_helper import get_logger_module

class File_Reader(object):
    def __init__(self, output_queue):
        self.log = get_logger_module(self.__class__.__name__)
        self._output_queue = output_queue
        self._stop_reading = False
        
    def read(self, path):
        if self._stop_reading:
            return
        self.log.debug("Verifying path '%s'",path)
        if os.path.isdir(path):
            self.log.debug("Path '%s' is a directory",path)
            for directory_entry in os.listdir(path):                
                try:
                    self.read(os.path.join(path, directory_entry))
                except ValueError:
                    pass #don't care about entries that are not files nor directories
        elif os.path.isfile(path):
            self.log.debug("Verifying file '%s'",path)
            self._output_queue.put(File_Info(path))
        else:
            raise ValueError("The path '%s' is not a file or directory" % path)
        self.log.debug("Path '%s' read",path)
        
    def stop(self):
        self._stop_reading = True