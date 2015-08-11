from circuits import Component

from fcb.framework import events
from fcb.utils.log_helper import get_logger_module


class Pipeline(Component):
    """
    Represents a pipeline of work (composed of PipelineTasks)
    """
    _task_chain = []
    log = get_logger_module("Pipeline")

    def add(self, task):
        if task is None:
            return self
        if self._task_chain:
            self._task_chain[-1].next_task(task)
        self.log.debug("Pipeline add task: {}".format(str(task)))
        self._task_chain.append(task)

        task.register(self)
        return self

    def add_in_list(self, tasks):
        if tasks is None:
            return self

        for task in tasks:
            self.add(task)
        return self

    def request_stop(self):
        self.fire(events.FlushPendings())
        self.fire(events.SystemShouldStop())
