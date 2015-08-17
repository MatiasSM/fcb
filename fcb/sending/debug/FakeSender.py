from fcb.framework.workers import default_worker_pool

from fcb.framework.workflow.SenderTask import SenderTask
from fcb.utils.log_helper import deep_print

_worker_pool = default_worker_pool


class FakeSender(SenderTask):
    # override from SenderTask
    def do_send(self, block):
        self.log.debug(deep_print(block, "Pseudo sending block:"))

    # override from HeavyPipelineTask
    def get_worker_channel(self):
        return _worker_pool.get_worker()

    # override from SenderTask
    def destinations(self):
        return ["Fake Destination"]
