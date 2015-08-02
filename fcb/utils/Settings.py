from copy import deepcopy
import os
import re
import tempfile
import xml.etree.ElementTree as Etree

from fcb.utils.log_helper import get_logger_for, deep_print


# --- helper functions ------------------------------


def _parse_bool(text):
    if text == "0" or text.lower() == "false":
        return False
    return bool(text)


def _value_builder(variable, node):
    if variable is None:
        return node.text

    var_type = type(variable)
    if var_type == bool:
        return _parse_bool(node.text)
    elif isinstance(variable, _PlainNode):
        return var_type(node)
    elif isinstance(variable, basestring):
        return var_type("" if node.text is None else node.text)
    else:
        return var_type(node.text)


def _parse_fields_in_root(instance, root):
    if root is None:
        return

    log = get_logger_for(instance)
    for node in root:
        if not _parse_field(instance, node):
            log.debug("Unknown setting {}. Will be ignored.".format(node.tag))


def _parse_field(instance, node):
    tag = node.tag
    try:
        attribute = getattr(instance, tag)
        setattr(instance, tag, _value_builder(attribute, node))
        return True
    except:
        pass
    return False


def _check_required_fields(instance, fields):
    for field in fields:
        if getattr(instance, field) is None:
            raise Exception("Field {} not set".format(field))


# --------------- sections and helpful parsers ---------------


class _Size(object):
    in_bytes = 0

    _parse_regex = re.compile("^ *([0-9]+) *([kK]|[mM]|[gG]| *) *$")
    _unit_factor = {'g': 1000 ** 3, 'm': 1000 ** 2, 'k': 1000, '': 1}

    def __init__(self, size_str):
        log = get_logger_for(self)
        result = self._parse_regex.match(size_str)
        if result is not None:
            self.in_bytes = int(result.group(1)) * self._unit_factor[result.group(2).strip().lower()]
            log.debug("String '%s' parsed as '%d' bytes", size_str, self.in_bytes)
        else:
            raise RuntimeError("'%s' is not a valid size string" % size_str)


class _PlainNode(object):
    def load(self, root):
        _parse_fields_in_root(self, root)


class _Performance(_PlainNode):
    threads = 1
    max_pending_for_processing = 10

    def __init__(self, root=None):
        self.load(root)


class _RateLimits(_PlainNode):
    up_kbytes_sec = None

    def __init__(self, root=None):
        self.load(root)


class _GlobalLimits(object):
    max_shared_upload_per_day = _Size("0")
    stop_on_remaining = _Size("0")
    max_file_size = _Size("0")
    rate_limits = None

    def __init__(self, root=None):
        if root is not None:
            for node in root:
                tag = node.tag
                if tag == "rate_limits":
                    self.rate_limits = _RateLimits(node)
                else:
                    _parse_field(self, node)


class _Limits(_PlainNode):
    # recognized fields (0 means, no limit)
    max_upload_per_day = _Size("0")
    max_container_content_size = _Size("1G")
    max_files_per_container = 0

    def __init__(self, root=None):
        self.load(root)


class _StoredFiles(_PlainNode):
    should_encrypt = True
    should_check_already_sent = True
    delete_temp_files = True
    tmp_file_parts_basepath = tempfile.gettempdir()
    should_split_small_files = False

    def __init__(self, root=None):
        self.load(root)


class _CipherSettings(object):
    performance = None

    def __init__(self, root=None, default_performance=None):
        self.performance = deepcopy(default_performance) if default_performance is not None else _Performance()
        if root is not None:
            for node in root:
                tag = node.tag
                if tag == "performance":
                    self.performance.load(node)


class _MailAccount(object):
    class Source(_PlainNode):
        mail = None
        user = None
        password = None
        server = None
        server_port = None
        use_ssl = False

        def __init__(self, root):
            self.load(root)
            if self.server_port is None:
                self.server_port = 465 if self.use_ssl else 25
            _check_required_fields(self, ["mail", "user", "password", "server"])

    limits = None
    src = None
    subject_prefix = ""
    dst_mails = None
    retries = 3
    time_between_retries = 5

    def __init__(self, root, default_limits):
        self.limits = deepcopy(default_limits) if default_limits is not None else _Limits()
        for node in root:
            tag = node.tag
            if tag == "limits":
                self.limits.load(node)
            elif tag == "src":
                self.src = self.Source(node)
            elif tag == "dst_mail":
                if self.dst_mails is None:
                    self.dst_mails = [node.text]
                else:
                    self.dst_mails.append(node.text)
            else:
                _parse_field(self, node)

        _check_required_fields(self, ["src", "dst_mails"])

    @property
    def destinations(self):
        return self.dst_mails


class _DirDestination(object):
    limits = None
    path = None

    def __init__(self, root, default_limits):
        self.limits = deepcopy(default_limits) if default_limits is not None else _Limits()
        for node in root:
            tag = node.tag
            if tag == "limits":
                self.limits.load(node)
            else:
                _parse_field(self, node)

        _check_required_fields(self, ["path"])

        log = get_logger_for(self)
        conf_path = self.path
        self.path = os.path.abspath(conf_path)
        log.debug("Configured path '{}' interpreted as absolute path '{}'".format(conf_path, self.path))

    @property
    def destinations(self):
        return [self.path]


class _MegaSenderSettings(_PlainNode):
    limits = None
    user = None
    password = None
    dst_path = ""
    verify_access = False

    def __init__(self, root, default_limits):
        self.limits = deepcopy(default_limits) if default_limits is not None else _Limits()
        for node in root:
            tag = node.tag
            if tag == "limits":
                self.limits.load(node)
            else:
                _parse_field(self, node)
        self.dst_path = "/".join(("/Root", self.dst_path))  # use Root as base

    @property
    def destinations(self):
        return ["mega" if self.user is None else "mega: " + self.user]


class _SlowSenderSettings(_PlainNode):
    sleep_time = 5

    def __init__(self, root=None):
        self.load(root)

    @property
    def destinations(self):
        return ["slow_sender"]


class _ToImage(_PlainNode):
    enabled = False

    def __init__(self, root=None):
        self.load(root)


class _Debugging(_PlainNode):
    enabled = False

    def __init__(self, root=None):
        self.load(root)


class _ExcludePaths(object):
    path_filter_list = []

    def __init__(self, root=None):
        if root is None:
            return

        for node in root:
            tag = node.tag
            if tag == "file_name":
                self.path_filter_list.append(self._get_file_regex(node.text))
            if tag == "dir_name":
                self.path_filter_list.append(self._get_dir_regex(node.text))
            if tag == "regex_file_name":
                self.path_filter_list.append(self._get_re_file_regex(node.text))
            if tag == "regex_dir_name":
                self.path_filter_list.append(self._get_re_dir_regex(node.text))
            if tag == "regex":
                self.path_filter_list.append(node.text)
            else:
                _parse_field(self, node)

    @staticmethod
    def _get_dir_regex(dir_name):
        return _ExcludePaths._get_re_dir_regex(re.escape(dir_name))

    @staticmethod
    def _get_re_dir_regex(re_dir_pattern):
        return "".join((
            "^(?:.*/)?",
            re_dir_pattern,
            "/?$"
        ))

    @staticmethod
    def _get_file_regex(file_name):
        return _ExcludePaths._get_re_file_regex(re.escape(file_name))

    @staticmethod
    def _get_re_file_regex(re_file_pattern):
        return "".join((
            "^(?:.*/)?",
            re_file_pattern,
            "$"
        ))

# ----- Settings -----------------------


class InvalidSettings(Exception):
    def __init__(self, error_msg="", invalid_setting=None):
        super(self.__class__, self)\
            .__init__("".join((error_msg, "" if invalid_setting is None else deep_print(invalid_setting))))


class Settings(object):
    performance = _Performance()
    limits = _GlobalLimits()
    _default_limits = _Limits()
    exclude_paths = _ExcludePaths()
    stored_files = _StoredFiles()
    cipher = _CipherSettings()
    mail_accounts = []
    sent_files_log = None
    dir_dest = None
    to_image = _ToImage()
    add_fake_sender = False
    mega_settings = None
    slow_sender = None
    debugging = _Debugging()

    def __init__(self, file_path):
        self._parse(Etree.parse(file_path))

    def _parse(self, tree):
        log = get_logger_for(self)

        cipher_node = None
        ms_node = None
        dir_dest_node = None
        mega_dest_node = None
        for node in tree.getroot():
            tag = node.tag
            if tag == "performance":
                self.performance = _Performance(node)
            elif tag == "exclude_paths":
                self.exclude_paths = _ExcludePaths(node)
            elif tag == "limits":
                self.limits = _GlobalLimits(node)
            elif tag == "default_limits":
                self._default_limits = _Limits(node)
            elif tag == "stored_files":
                self.stored_files = _StoredFiles(node)
            elif tag == "to_image":
                self.to_image = _ToImage(node)
            elif tag == "sent_files_log":
                _parse_field(self, node)
            elif tag == "cipher":
                cipher_node = node  # we keep it until we have processed other tags (we need performance loaded)
            elif tag == "mail_sender":
                ms_node = node  # we keep it until we have processed other tags (we need limits loaded)
            elif tag == "dir_destination":
                dir_dest_node = node  # we keep it until we have processed other tags (we need limits loaded)
            elif tag == "fake_sender":
                self.add_fake_sender = True
            elif tag == "mega_sender":
                mega_dest_node = node
            elif tag == "slow_sender":
                self.slow_sender = _SlowSenderSettings(node)
            elif tag == "debugging":
                self.debugging = _Debugging(node)
            else:
                log.warning("Tag '%s' not recognized. Will be ignored.", tag)

        if cipher_node is not None:
            self.cipher = _CipherSettings(cipher_node, self.performance)

        if ms_node is not None:
            for sub_node in ms_node.iter("account"):
                self.mail_accounts.append(_MailAccount(sub_node, self._default_limits))

        if dir_dest_node is not None:
            self.dir_dest = _DirDestination(dir_dest_node, self._default_limits)

        if mega_dest_node is not None:
            self.mega_settings = _MegaSenderSettings(mega_dest_node, self._default_limits)
