import xml.etree.ElementTree as Etree

from fcb.utils.log_helper import get_logger_for


class _MailConf(object):
    def __init__(self, root):
        self.user = root.find("user").text
        self.password = root.find("password").text
        self.mail_server = root.find("pop_server").text


class _MegaConf(object):
    def __init__(self, root):
        self.user = self._get_optional(root, "user")
        self.password = self._get_optional(root, "password")
        self.dst_path = self._get_optional(root, "dst_path", "")

    @staticmethod
    def _get_optional(root, node_id, default=None):
        node = root.find(node_id)
        return node.text if node is not None else default


# FIXME not pythonic nor flexible enough
class Configuration(object):
    def __init__(self, file_path):
        self.log = get_logger_for(self)
        self.mail_confs = []
        self.mega_confs = []

        self._parse(Etree.parse(file_path))

    def _parse(self, tree):
        for child in tree.getroot():
            try:
                if child.tag == "mail_account":
                    self.mail_confs.append(_MailConf(child))
                elif child.tag == "mega_sender":
                    self.mega_confs.append(_MegaConf(child))
                else:
                    self.log.warning("Tag '%s' not recognized. Will be ignored.", child.tag)
            except RuntimeError as e:
                    self.log.error(e)
