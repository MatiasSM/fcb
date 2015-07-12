"""
This launcher is used to be able to limit upload rate
It checks if a rate limit is configured and, in that case, wraps the execution in trickle
Otherwise it executes the same as using directly files_cloud_backuper.py
"""

import os
import sys
import signal
from subprocess32 import call
from distutils.spawn import find_executable
from fcb.utils import trickle

from fcb.utils.Settings import Settings
from fcb.utils.log_helper import get_logger_module
import logging

# noinspection PyUnresolvedReferences
import fcb.log_configuration

# disable logging except for this module (extra logging is deferred to the subprocess)
fcb.log_configuration.logger.setLevel(logging.NOTSET)
log = get_logger_module('main')
log.setLevel(fcb.log_configuration.level)


def get_direct_executable():
    pip_exec = find_executable("fcb-direct-upload")  # tries to find pip installed executable
    if pip_exec is None:
        # tries to find python (to execute by hand). Note: this may fail if a different python should be used
        python_exec = find_executable("python")
        cur_dir = os.path.dirname(os.path.realpath(__file__))
        executable = [python_exec, os.path.join(cur_dir, "files_cloud_backuper.py")]
    else:
        executable = [pip_exec]

    if executable is None:
        raise RuntimeError("Couldn't determine direct fcb executable")

    return executable


def mute_signals():
    for i in [x for x in dir(signal) if (x.startswith("SIG") and not x.startswith("SIG_"))]:
        try:
            signum = getattr(signal, i)
            signal.signal(signum, lambda *args: None)
        except RuntimeError:
            pass


def main():
    if len(sys.argv) < 3:
        log.error("Usage: %s <config_file> <input path> [<input path> ...]", sys.argv[0])
        exit(1)

    fcb_direct_exec = get_direct_executable() + sys.argv[1:]
    settings = Settings(sys.argv[1])

    if settings.limits.rate_limits is not None:
        rate_limiter = trickle.TrickleBwShaper(trickle.Settings(settings.limits.rate_limits))
        fcb_direct_exec = rate_limiter.wrap_call(fcb_direct_exec)

    mute_signals()  # Mute signals. The one handling them will be the subprocess
    log.debug("Executing: %s", fcb_direct_exec)
    call(fcb_direct_exec)

if __name__ == '__main__':
    main()
