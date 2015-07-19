from fcb.framework.workflow.SenderTask import SenderTask
from fcb.utils.log_helper import deep_print


class FakeSender(SenderTask):
    # override from SenderTask
    def do_send(self, block):
        self.log.debug(deep_print(block, "Pseudo sending block:"))

    # override from SenderTask
    def destinations(self):
        return ["Fake Destination"]
