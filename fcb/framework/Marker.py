from fcb.framework.events import Mark
from fcb.framework.workflow.PipelineTask import PipelineTask


class Marks(object):
    sending_stage = "sending_stage"
    end_of_pipeline = "end_of_pipeline"


class MarkerTask(PipelineTask):
    """
    Issues an events.Mark every time its process_data is called
    """
    _mark = None

    def do_init(self, mark):
        self._mark = mark

    # override from PipelineTask
    def process_data(self, block):
        self.fire(Mark(self._mark, block))
        return block
