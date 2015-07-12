import time

from fcb.framework.workflow.PipelineTask import PipelineTask


class SlowSender(PipelineTask):

    def __init__(self, settings):
        PipelineTask.__init__(self)

        self._sleep_time = settings.sleep_time

    # override from PipelineTask
    def process_data(self, block):
        self.log.debug("Slow sending block. Sleep %d", self._sleep_time)
        time.sleep(self._sleep_time)
        return block
