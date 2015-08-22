from circuits.core.events import Event


class NewInputPath(Event):
    """
    :argument path (str)
    """
    pass


class NewFileToProcess(Event):
    """
    :argument FileInfo
    """
    success = True


class NewContainerFile(Event):
    """
    :argument Block
    """


class FilteredFile(Event):
    """
    :argument FileInfo/Block
    """


class FileConsumed(Event):
    """
    Represents a file info consumed (will be transformed or is buffered)
    :argument FileInfo
    """


class PathConsumed(Event):
    """
    Represents a file path which didn't lead to a file processing
    :argument FilePath
    """


class FlushPendings(Event):
    pass


class SystemShouldStop(Event):
    """
    Represents an event which signals that the system should stop
    """
    channel = "control_shutdown"


class TransmissionQuotaReached(SystemShouldStop):
    pass


class NoMoreInput(SystemShouldStop):
    pass


class Mark(Event):
    """
    :argument Mark
    :argument Data (processed in pipeline)
    """
