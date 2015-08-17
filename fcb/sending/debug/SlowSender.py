import time

from fcb.framework.workers import default_worker_pool
from fcb.framework.workflow.SenderTask import SenderTask

_worker_pool = default_worker_pool


class SlowSender(SenderTask):
    _sleep_time = None

    def do_init(self, settings):
        super(SlowSender, self).do_init()
        self._sleep_time = settings.sleep_time

    # override from SenderTask
    def do_send(self, block):
        self.log.debug("Slow sending block. Sleep %d", self._sleep_time)
        time.sleep(self._sleep_time)

    # override from HeavyPipelineTask
    def get_worker_channel(self):
        return _worker_pool.get_worker()

    # override from SenderTask
    def destinations(self):
        return []  # this is not a real sender (don't mark it as such) FIXME ugly
