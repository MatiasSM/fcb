from signal import SIGINT

from circuits import Component, handler, BaseComponent

from circuits.core.events import signal

from fcb.framework import events
from fcb.framework.Marker import Marks
from fcb.utils.log_helper import get_logger_module


class _GlobalWorkflowController(BaseComponent):
    log = get_logger_module("_GlobalWorkflowController")

    _should_stop = False
    _send_remaining = 0

    @handler(events.Mark.__name__)
    def on_mark(self, mark, *_):
        if mark == Marks.sending_stage:
            self._mark_new_sending()
        elif mark == Marks.end_of_pipeline:
            self._mark_sent()
        self.check_end_condition()

    @handler(events.SystemShouldStop.__name__)
    def should_stop(self):
        self._should_stop = True
        self.check_end_condition()

    def check_end_condition(self):
        self.log.debug("Send remaining %d", self._send_remaining)
        if self._send_remaining == 0:
            self._stop_if_required()

    def _stop_if_required(self):
        if self._should_stop:
            raise SystemExit(0)

    def _mark_new_sending(self):
        self._send_remaining += 1

    def _mark_sent(self):
        self._send_remaining -= 1


class Pipeline(Component):
    """
    Represents a pipeline of work (composed of PipelineTasks)
    """
    _task_chain = []
    _to_disable_on_shutdown = []
    log = get_logger_module("Pipeline")

    def init(self):
        _GlobalWorkflowController().register(self)  # will handle system termination
        pass

    def add(self, task, disable_on_shutdown=False):
        if task is None:
            return self

        if self._task_chain:
            self._task_chain[-1].next_task(task)

        self.log.debug("Pipeline add task: {}".format(str(task)))
        self._task_chain.append(task)
        if disable_on_shutdown:
            self._to_disable_on_shutdown.append(task)

        task.register(self)
        return self

    def add_in_list(self, tasks, disable_on_shutdown=False):
        if tasks is None:
            return self

        for task in tasks:
            self.add(task=task, disable_on_shutdown=disable_on_shutdown)
        return self

    @handler(signal.__name__, priority=10)
    def _on_signal(self, event, signo, *_):
        if signo == SIGINT:
            self.request_stop()
            event.stop()  # we will finish up

    def request_stop(self):
        for task in self._to_disable_on_shutdown:
            task.disable()
        self.fire(events.FlushPendings())
        self.fire(events.SystemShouldStop())
