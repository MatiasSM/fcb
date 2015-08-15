from circuits import Event, task, BaseComponent
from circuits.core.handlers import handler

from fcb.framework.workflow.PipelineTask import PipelineTask


class _ToNextHandler(Event):
    pass


class _ToNextPasser(BaseComponent):
    _to_next = None

    def init(self, to_next_function):
        self.channel = self.__class__.__name__ + str(id(self))
        self._to_next = to_next_function

    @handler(_ToNextHandler.__name__)
    def _handle_to_next(self, block):
        self._to_next(block)


class HeavyPipelineTask(PipelineTask):
    _to_next_channel = None

    """
    Represents a PipelineTask that requires a circuits.task to process its data
    """

    def do_init(self, *args, **kwargs):
        to_next = _ToNextPasser(to_next_function=lambda block: PipelineTask.hand_on_to_next_task(self, block))
        self._to_next_channel = to_next.channel
        to_next.register(self)

    # override from PipelineTask
    def process_data(self, block):
        self.log.debug("New block to process: %s", block)
        self.fire(task(self._do_task, block), self.get_worker_channel())  # get inside the event handling framework

    def _do_task(self, block):
        new_data = self.do_heavy_work(block)
        if new_data is not None:
            self.hand_on_to_next_task(new_data)

    # override from PipelineTask
    def hand_on_to_next_task(self, block):
        self.log.debug("Will fire to next handler with block %s", block)
        self.fire(_ToNextHandler(block), self._to_next_channel)

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
