from utils.log_helper import get_logger_module


class FakeSender(object):
    def __init__(self):
        self.log = get_logger_module(self.__class__.__name__)

    def send(self, block):
        # TODO deep print
        self.log.debug("Pseudo sending block: %s", str(block.__dict__))
        if not hasattr(block, 'send_destinations'):
            block.send_destinations = []
        block.send_destinations.append("Fake Destination")

    def close(self):
        pass
