from circuits import Event, task
from circuits.core.handlers import handler
from fcb.framework.workflow.PipelineTask import PipelineTask


class HeavyPipelineTask(PipelineTask):
    """
    Represents a PipelineTask that requires a circuits.task to process its data
    """

    # override from PipelineTask
    def process_data(self, block):
        self.fire(task(self._do_task, block), self.get_worker_channel())  # get inside the event handling framework

    def _do_task(self, block):
        new_data = self.do_heavy_work(block)
        self.hand_on_to_next_task(new_data)

    def get_worker_channel(self):
        """
        Should be redefined by sub-classes if a special channel is required to communicate with the Worker
        :return: the circuits channel which should be used to generate the task to do the heavy work
        """
        return None

    def do_heavy_work(self, data):
        """
        Subclasses must redefine this method to do the heavy work required

        :param data: same as received by PipelineTask::handle_data

        :return: new data (to pass by in the pipeline)
        """
        return None
