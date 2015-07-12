import code
import traceback
import signal
import sys

from fcb.utils.log_helper import get_logger_module

_log = get_logger_module("debugging")


# logic taken from http://stackoverflow.com/questions/132058/showing-the-stack-trace-from-a-running-python-application
def attach_debugger(sig, frame):
    """Interrupt running process, and provide a python prompt for
    interactive debugging."""
    d = {'_frame': frame}  # Allow access to frame object.
    d.update(frame.f_globals)  # Unless shadowed by global
    d.update(frame.f_locals)

    i = code.InteractiveConsole(d)
    message = "Signal received : entering python shell.\nTraceback:\n"
    message += ''.join(traceback.format_stack(frame))
    i.interact(message)


# Adapted from http://bzimmer.ziclix.com/2008/12/17/python-thread-dumps/
def gen_stacktraces():
    stacktrace = []
    for threadId, stack in sys._current_frames().items():
        stacktrace.append("\n# ThreadID: %s" % threadId)
        for filename, lineno, name, line in traceback.extract_stack(stack):
            stacktrace.append('File: "%s", line %d, in %s' % (filename, lineno, name))
            if line:
                stacktrace.append("  %s" % (line.strip()))

    return "\n".join(stacktrace)


def print_stacktraces(*_):
    _log.critical(gen_stacktraces())


def configure_signals():
    signal.signal(signal.SIGUSR1, attach_debugger)
    signal.signal(signal.SIGUSR2, print_stacktraces)
