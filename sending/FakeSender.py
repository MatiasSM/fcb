from framework.PipelineTask import PipelineTask


class FakeSender(PipelineTask):
    # override from PipelineTask
    def process_data(self, block):
        # TODO deep print
        self.log.debug("Pseudo sending block: %s", str(block.__dict__))
        if not hasattr(block, 'send_destinations'):
            block.send_destinations = []
        block.send_destinations.append("Fake Destination")
