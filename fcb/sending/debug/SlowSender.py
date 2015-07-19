import time

from fcb.framework.workflow.SenderTask import SenderTask


class SlowSender(SenderTask):
    def __init__(self, settings):
        SenderTask.__init__(self)

        self._sleep_time = settings.sleep_time

    # override from SenderTask
    def do_send(self, block):
        self.log.debug("Slow sending block. Sleep %d", self._sleep_time)
        time.sleep(self._sleep_time)

    # override from SenderTask
    def destinations(self):
        return []  # this is not a real sender (don't mark it as such) FIXME ugly
