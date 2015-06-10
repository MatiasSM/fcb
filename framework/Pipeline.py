import itertools


class Pipeline(object):
    """
    Represents a pipeline of work (composed of PipelineTasks)
    """
    _task_chain = []

    class _Link(object):
        """
        Represents a link in the pipeline
        """
        def __init__(self, task_list, pipeline):
            self.task_list = task_list
            self.pipeline = pipeline

        def add_in_list(self, tasks, output_queue):
            if tasks is None:
                return self
            for task in tasks:
                self._connect(task)
            return self.pipeline.add_in_list(tasks, output_queue)

        def add_many(self, task_builder, output_queue, num_of_tasks):
            if task_builder is None:
                return self
            new_link = self.pipeline.add_many(task_builder, output_queue, num_of_tasks)
            for task in new_link.task_list:
                self._connect(task)
            return new_link

        def add(self, task, output_queue):
            if task is None:
                return self
            self._connect(task)
            return self.pipeline.add(task, output_queue)

        def _connect(self, task):
            for in_link in self.task_list:
                ''' Note: in current impl, all tasks share the same output_queue, have only one input queue and
                    don't keep any other information about connected tasks. So this is the same as calling
                    connect_to_output for only one task in the list.
                    However, calling for everyone feels better and keeps the code working if we want to do something
                    else when connecting
                '''
                in_link.connect_to_output(task)

    def add_in_list(self, tasks, output_queue):
        for task in tasks:
            task.output_queue(output_queue)
        self._task_chain.extend(tasks)
        return self._Link(tasks, self)

    def add_many(self, task_builder, output_queue, num_of_tasks):
        """
        Adds many tasks associated to the same output queue

        :param task_builder: functor to build the tasks
        :param output_queue: output queue for the tasks
        :param num_of_tasks: amount of tasks to add
        """
        tasks = []
        for _ in itertools.repeat(None, num_of_tasks):
            task = task_builder()
            task.output_queue(output_queue)
            tasks.append(task)
        self._task_chain.extend(tasks)
        return self._Link(tasks, self)

    def add(self, task, output_queue):
        task.output_queue(output_queue)
        self._task_chain.append(task)
        return self._Link((task,), self)

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
