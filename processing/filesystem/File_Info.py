
from utils import digest 
import os

class File_Info:
    def __init__(self, path):
        self._path = path
        self._sha1 = None
        self._size = None
        
    @property
    def path(self):
        return self._path
    
    @property
    def sha1(self):
        if not self._sha1:
            self._sha1 = digest.gen_sha1(self._path)            
        return self._sha1
    
    @property
    def size(self):
        ''' size in bytes '''
        if not self._size:
            self._size = os.path.getsize(self._path)            
        return self._size
    
    @property
    def basename(self):
        return os.path.basename(self._path)
        
    def __str__(self):
        return "%s (sha1 '%s')" % (self._path, str(self._sha1))
        
    