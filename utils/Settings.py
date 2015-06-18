from copy import deepcopy
import os
import re
import tempfile
import xml.etree.ElementTree as Etree

from utils.log_helper import get_logger_for


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


class _Limits(_PlainNode):
    # recognized fields (0 means, no limit)
    max_upload_per_day = _Size("0")
    max_size = _Size("0")
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

# ----- Settings -----------------------


class Settings(object):
    performance = _Performance()
    _limits = _Limits()
    stored_files = _StoredFiles()
    cipher = _CipherSettings()
    mail_accounts = []
    sent_files_log = None
    dir_dest = None

    def __init__(self, file_path):
        self._parse(Etree.parse(file_path))

    def _parse(self, tree):
        log = get_logger_for(self)

        cipher_node = None
        ms_node = None
        dir_dest_node = None
        for node in tree.getroot():
            tag = node.tag
            if tag == "performance":
                self.performance = _Performance(node)
            elif tag == "limits":
                self._limits = _Limits(node)
            elif tag == "stored_files":
                self.stored_files = _StoredFiles(node)
            elif tag == "sent_files_log":
                _parse_field(self, node)
            elif tag == "cipher":
                cipher_node = node  # we keep it until we have processed other tags (we need performance loaded)
            elif tag == "mail_sender":
                ms_node = node  # we keep it until we have processed other tags (we need limits loaded)
            elif tag == "dir_destination":
                dir_dest_node = node  # we keep it until we have processed other tags (we need limits loaded)
            else:
                log.warning("Tag '%s' not recognized. Will be ignored.", tag)

        if cipher_node is not None:
            self.cipher = _CipherSettings(cipher_node, self.performance)

        if ms_node is not None:
            for sub_node in ms_node.iter("account"):
                self.mail_accounts.append(_MailAccount(sub_node, self._limits))

        if dir_dest_node is not None:
            self.dir_dest = _DirDestination(dir_dest_node, self._limits)
