import itertools

from framework.PipelineTaskGroup import PipelineTaskGroup
from utils.log_helper import get_logger_module


class Pipeline(object):
    """
    Represents a pipeline of work (composed of PipelineTasks)
    """
    _task_chain = []
    log = get_logger_module("Pipeline")

    def add(self, task, output_queue):
        task.output_queue(output_queue)
        if self._task_chain:
            self._task_chain[-1].connect_to_output(task)
        self.log.debug("Pipeline add task: {}".format(str(task)))
        self._task_chain.append(task)
        return self

    def add_in_list(self, tasks, output_queue):
        group = PipelineTaskGroup(output_queue=output_queue)
        group.add_many(tasks)
        return self.add(task=group, output_queue=output_queue)

    def add_many(self, task_builder, output_queue, num_of_tasks):
        """
        Adds many tasks associated to the same output queue

        :param task_builder: functor to build the tasks
        :param output_queue: output queue for the tasks
        :param num_of_tasks: amount of tasks to add
        """
        return self.add_in_list(
            tasks=[task_builder() for _ in itertools.repeat(None, num_of_tasks)],
            output_queue=output_queue)

    def start_all(self):
        """
        start the tasks in the pipeline in reverse order
        """
        for task in reversed(self._task_chain):
            task.start()

    def stop_all(self):
        # note we stop according to the pipeline order
        for task in self._task_chain:
            task.stop()

    def wait_next_to_stop(self, timeout):
        """
        Waits for the closest to the beginning alive task in the pipeline to stop
        :param timeout: max amount of time to wait
        :return: True if some waiting was done
                 False if there weren't any alive task next
        """
        for task in self._task_chain:
            if task.is_alive():
                task.join(timeout)
                return True
        return False
