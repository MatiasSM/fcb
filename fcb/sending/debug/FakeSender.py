from circuits import Worker

from fcb.framework.workflow.SenderTask import SenderTask
from fcb.utils.log_helper import deep_print


class FakeSender(SenderTask):
    _worker = Worker()

    # override from SenderTask
    def do_send(self, block):
        self.log.debug(deep_print(block, "Pseudo sending block:"))

    # override from HeavyPipelineTask
    def get_worker_channel(self):
        return self._worker

    # override from SenderTask
    def destinations(self):
        return ["Fake Destination"]
