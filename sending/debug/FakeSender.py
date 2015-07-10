from framework.workflow.PipelineTask import PipelineTask
from utils.log_helper import deep_print


class FakeSender(PipelineTask):
    # override from PipelineTask
    def process_data(self, block):

        self.log.debug(deep_print(block, "Pseudo sending block:"))
        if not hasattr(block, 'send_destinations'):
            block.send_destinations = []
        block.send_destinations.append("Fake Destination")
        return block
