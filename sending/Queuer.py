
class Queuer(object):
    def __init__(self,output_queue):
        self._out_queue = output_queue
        
    def send(self, block):
        self._out_queue.put(block)

    def close(self):
        pass