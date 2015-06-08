from threading import Thread

from utils.log_helper import get_logger_module

class Task(object):
    
    def __init__(self, threads_count, activity, activity_args, 
                 activity_stop = None, activity_stop_args = None, name=None):
        '''
            threads_count: amount of threads this task will execute on
            activity: callable to be executed by the threads (note it will be called once by each thread)
            activity_args: (tuple or dict) arguments to pass to the "activity"
            activity_stop: callable to be executed to tell the "activity" to stop 
                            (note it will be called once for each thread)
            activity_stop_args: (tuple or dict) arguments to pass to the "activity_stop"(if None, no argument is passed)
        '''
        self.log = get_logger_module(self.__class__.__name__)
        self._threads_count = threads_count
        self._activity = activity
        self._activity_kwargs = {}
        self._activity_args = ()
        if type(activity_args) == dict:
            self._activity_kwargs = activity_args
        else:
            self._activity_args = activity_args
        self._activity_stop = activity_stop
        self._activity_stop_args = activity_stop_args
        self._threads = []
        self._name = name
        
    def start(self):
        if self._name:
            self.log.debug("Starting '%s' with %d threads."%(self._name, self._threads_count))
        for _ in range(self._threads_count):
            thread = Thread(target = self._activity, args = self._activity_args, kwargs = self._activity_kwargs)
            thread.daemon = True
            self._threads.append(thread)
            thread.start()
      
    def request_stop(self):
        if self._name:
            self.log.debug("Requesting '%s' to stop.",self._name)
        if self._activity_stop:
            for _ in range(self._threads_count):
                if self._activity_stop_args:
                    if type(self._activity_stop_args) == dict:
                        self._activity_stop(**self._activity_stop_args)
                    else:
                        self._activity_stop(*self._activity_stop_args)
                else:
                    self._activity_stop()
            
    def stop(self):
        ''' requests the threads to stop and wait until they finish '''
        self.request_stop()
        self.wait()        
                
    def wait(self, timeout=None):
        for thread in self._threads:
            thread.join(timeout)
            
        if not self.is_alive() and self._name:
            self.log.debug("Task '%s' has all its threads stopped.",self._name)
        
    def is_alive(self):
        for thread in self._threads:
            if thread.isAlive():
                #self.log.debug("Thread %d is still alive. %s" % 
                #                (thread.ident, "Task %s" % self._name if self._name else ""))
                return True
        return False