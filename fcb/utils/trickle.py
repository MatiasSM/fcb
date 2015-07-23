from copy import deepcopy
from distutils.spawn import find_executable


class Settings(object):
    _upload_limit = 0

    def __init__(self, settings=None):
        if settings:
            self._upload_limit = settings.up_kbytes_sec

    @property
    def upload_limit(self):
        """ Returns the value as required by the trickle command (i.e. in KBytes) """
        return self._upload_limit

    def upload_limit_in_kbytes(self, upload_limit):
        self._upload_limit = upload_limit if upload_limit is not None else 0

    def to_argument_list(self):
        """
        converts the setting in a list as required by the trickle command
        """
        return ["-u", self._upload_limit] if self._upload_limit != 0 else []


class TrickleBwShaper(object):
    _trickle_cmd = "trickle"

    """
    Helper class to handle trickle (http://linux.die.net/man/1/trickle) usage
    """
    def __init__(self, settings):
        self._settings = deepcopy(settings)

        self._trickle_cmd = find_executable("trickle")
        if self._trickle_cmd is None:
            raise RuntimeError("Couldn't find 'trickle' program")

    def wrap_call(self, call_cmd):
        """
        "wraps" the call_cmd so it can be executed by subprocess.call (and related flavors) as "args" argument

        :param call_cmd: original args like argument (string or sequence)

        :return: a sequence with the original command "executed" under trickle
        """

        if isinstance(call_cmd, basestring):  # FIXME python 3 unsafe
            call_cmd = [call_cmd]

        return [self._trickle_cmd, "-s"] + self._settings.to_argument_list() + list(call_cmd)
