from collections import Callable
import threading
from circuits import BaseComponent, Event, handler

from fcb.utils.log_helper import get_logger_module


class SinkTask(object):
    """
    End of pipeline
    """

    def handle_data(self, data):
        pass


class PipelineTask(BaseComponent):
    """
    Represents a task in a pipeline

    Subclasses must override "process_data" method to implement their logic
    """
    log = None
    _next_task = None

    def init(self, next_task=None, *args, **kwargs):
        self.log = get_logger_module(self.__class__.__name__)
        self.next_task(next_task)
        if hasattr(self, "do_init") and isinstance(self.do_init, Callable):
            self.do_init(*args, **kwargs)

    def next_task(self, next_task):
        self._next_task = SinkTask() if next_task is None else next_task

    def handle_data(self, data):
        new_data = self.process_data(data)
        if new_data is not None:
            self.hand_on_to_next_task(new_data)

    def hand_on_to_next_task(self, data):
        self._next_task.handle_data(data)

    # noinspection PyMethodMayBeStatic
    def process_data(self, data):
        """
        Implements the logic of the task by processing a piece of data.

        As a convenience, if something is returned from the call, hand_on_to_next_task is called with it

        :param data: piece of data to process

        :return: an element to hand_on_to_next_task or None if not ready yet
                (the method will need to be called by the subclass)
        """
        return None
