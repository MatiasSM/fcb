from Queue import Queue
import threading

from fcb.utils.log_helper import get_logger_module


class ParallelTaskGroup(threading.Thread):
    """
    Groups a set of tasks to work together

    Note: differently from PipelineTask, this class is not designed to be extended
    """

    def __init__(self, name=None, input_queue=None, output_queue=None):
        threading.Thread.__init__(self, name=name if name is not None else self.__class__.__name__)
        self.log = get_logger_module(self.name)
        self._tasks = []
        self._input_queue = input_queue
        self._tasks_input_queue = Queue(1)
        self._output_queue = output_queue

    def __str__(self):
        return "{inq} -> {tasklist} -> {outq}"\
            .format(inq=str(self._input_queue), tasklist=self._tasks, outq=str(self._output_queue))

    def run(self):
        self.log.info("Running...")
        self.log.debug("Starting tasks")
        for task in self._tasks:
            task.start()

        data = self._get_data_to_process()
        while data is not None:
            self._tasks_input_queue.put(data)
            data = self._get_data_to_process()
        self._on_stop()
        self.log.debug("Finished processing loop")

    def add(self, task):
        """
        Adds the task to the group
        """
        self.log.debug("New task in group: %s", task.name)
        self._prevent_stop_propagation(task)
        task.input_queue(self._tasks_input_queue)
        task.output_queue(self._output_queue)
        self._tasks.append(task)
        self._tasks_input_queue.maxsize = len(self._tasks)

    def add_many(self, task_list):
        """
        Adds all the tasks in the task_list to the group
        """
        for task in task_list:
            self.add(task)

    def output_queue(self, output_queue):
        if output_queue is not self._output_queue:
            self._output_queue = output_queue
            for task in self._tasks:
                task.output_queue(self._output_queue)
        return self

    def input_queue(self, input_queue):
        """
        Associates input_queue to the group
        """
        self._input_queue = input_queue
        return self

    def connect_to_output(self, pipeline_task):
        """
        Makes the connection self -> pipeline_task
        """
        pipeline_task.input_queue(self._output_queue)

    def connect_to_input(self, pipeline_task):
        """
        Makes the connection pipeline_task -> self
        """
        pipeline_task.connect_to_output(self)

    def new_input(self, data):
        """
        Adds data to the input queue

        :param data: to be added to the input queue
        """
        if self._input_queue:
            self.log.debug("New input {}".format(data))
            self._input_queue.put(data)
        else:
            self.log.debug("No input queue to put data")

    def new_output(self, data):
        """
        Adds data to the output queue

        :param data: to be added to the output queue
        """
        if self._output_queue:
            self.log.debug("New output {}".format(data))
            self._output_queue.put(data)
        else:
            self.log.debug("No output queue to put data")

    def request_stop(self):
        self.log.debug("Requesting to stop.")
        self.new_input(None)  # note this will trigger general stop

    def _on_stop(self):
        self.log.debug("Propagating stopping process to group tasks...")
        '''
        first we request all tasks to stop, then we wait for them to stop
        This is needed because all tasks share the same input, and a None (stop) indicator can be processed
        by any other task (not the one originating it), so if we would wait for one specific to finish, we could
        hang
        '''
        for task in self._tasks:
            task.request_stop()

        for task in self._tasks:
            task.stop()
        self.distribute_end_of_processing()

    def stop(self):
        """
        Requests the tasks to stop and stops its own processing loop
        """
        self.log.debug("Stopping process started...")
        self.request_stop()
        self.join()
        self.log.info("Stopped.")

    def distribute_end_of_processing(self):
        """
        Implements the logic to distribute the end of processing
        """
        self.log.debug("Distributing end of processing")
        self.new_output(None)  # stops the next task in the pipeline

    def _get_data_to_process(self):
        """
        Gets next item to process from the input_queue if set

        :return: next item to process or None if there is no more items to process
        """
        if self._input_queue is not None:
            return self._input_queue.get()
        return None

    @staticmethod
    def _prevent_stop_propagation(task):
        """
        Bypass the task distribute_end_of_processing so it doesn't interfere with the group work
        """
        task.distribute_end_of_processing = lambda *args, **kw: None

