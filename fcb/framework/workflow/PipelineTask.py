import threading

from fcb.utils.log_helper import get_logger_module


class PipelineTask(threading.Thread):
    """
    Represents a task in a pipeline
    It may have an input queue and an output queue which are used to process pieces of information and generate new
    ones

    Subclasses must override "process_data" method to implement their logic
    """

    def __init__(self, name=None, input_queue=None, output_queue=None):
        threading.Thread.__init__(self, name=name if name is not None else self.__class__.__name__)
        self.log = get_logger_module(self.name)
        self._input_queue = input_queue
        self._output_queue = output_queue
        self._must_stop = False

    def __str__(self):
        return "{inq} -> {taskname} -> {outq}"\
            .format(inq=str(self._input_queue), taskname=self.name, outq=str(self._output_queue))

    # noinspection PyNoneFunctionAssignment
    def run(self):
        self.log.info("Running...")
        self.on_start()
        data = self.get_data_to_process()
        while data is not None and not self._must_stop:
            self.log.debug("New data: %s", data)
            result = self.process_data(data)
            if result is not None and self._output_queue is not None:
                self.log.debug("New (implicit) output: %s", result)
                self._unsafe_put_in_output(result)
            data = self.get_data_to_process()
        self.on_stopped()
        self.distribute_end_of_processing()
        self.log.debug("Finished processing loop")

    def request_stop(self):
        self.log.debug("Requesting to stop.")
        self._must_stop = True
        self.new_input(None)

    def stop(self):
        """
        Requests the thread to stop and wait until it finishes
        """
        self.request_stop()
        self.join()
        self.log.info("Stopped.")

    def new_input(self, data):
        """
        Adds data to the input queue

        :param data: to be added to the input queue
        """
        if self._input_queue:
            self.log.debug("New input %s (queue: %0.2x)", data, id(self._input_queue))
            self._input_queue.put(data)
        else:
            self.log.debug("No input queue to put data")

    def has_pending_input(self):
        return not self._input_queue.empty()

    def new_output(self, data):
        """
        Adds data to the output queue

        :param data: to be added to the output queue
        """
        if self._output_queue:
            self.log.debug("New output {}".format(data))
            self._unsafe_put_in_output(data)
        else:
            self.log.debug("No output queue to put data")

    def _unsafe_put_in_output(self, data):
        self._output_queue.put(data)

    def output_queue(self, output_queue):
        self._output_queue = output_queue
        return self

    def input_queue(self, input_queue):
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

    # ---------------- logic subclasses should/may overwrite
    def get_data_to_process(self):
        """
        Gets/Generate next item to process

        Default implementation take the next item from self._input_queue or returns None if self._input_queue is not set

        :return: next item to process or None if there is no more items to process (Task can stop)
        """
        if self._input_queue is not None:
            return self._input_queue.get()
        return None

    # noinspection PyMethodMayBeStatic
    def process_data(self, data):
        """
        Implements the logic of the task by processing a piece of data.

        As a convenience, if something is returned from the call, it is enqueued into self._output_queue

        :param data: pieces of data to process

        :return: an element to enqueue in the self._output_queue or None if nothing should be enqueued
        """
        return None

    # noinspection PyMethodMayBeStatic
    def on_start(self):
        """
        Executed when the task starts working
        """
        pass

    # noinspection PyMethodMayBeStatic
    def on_stopped(self):
        """
        Executed when the task finishes working
        """
        pass

    def distribute_end_of_processing(self):
        """
        Implements the logic to distribute the end of processing
        """
        self.log.debug("Distributing end of processing")
        self.new_output(None)  # stops the next task in the pipeline
