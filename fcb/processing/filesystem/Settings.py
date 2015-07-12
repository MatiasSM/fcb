from copy import deepcopy

from fcb.database.helpers import get_session
from fcb.database.schema import FilesDestinations
from fcb.utils.log_helper import get_logger_for


class _SenderRestriction(object):
    def __init__(self, sender_settings):
        self.max_upload_per_day_in_bytes = sender_settings.limits.max_upload_per_day.in_bytes
        self.max_container_content_size_in_bytes = sender_settings.limits.max_container_content_size.in_bytes
        self.max_files_per_container = sender_settings.limits.max_files_per_container

    def __eq__(self, other):
        return other \
               and self.max_upload_per_day_in_bytes == other.max_upload_per_day_in_bytes \
               and self.max_container_content_size_in_bytes == other.max_container_content_size_in_bytes \
               and self.max_files_per_container == other.max_files_per_container

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.max_upload_per_day_in_bytes,
                     self.max_container_content_size_in_bytes,
                     self.max_files_per_container))


class _SenderSpec(object):
    restrictions = None
    destinations = None
    bytes_uploaded_today = 0

    def __init__(self, sender_settings):
        log = get_logger_for(self)
        self.restrictions = _SenderRestriction(sender_settings)
        self.destinations = deepcopy(sender_settings.destinations)
        with get_session() as session:
            self.bytes_uploaded_today = \
                FilesDestinations.get_bytes_uploaded_in_date(session, self.destinations)
        log.info("According to the logs, it were already uploaded today %d bytes for destinations %s",
                 self.bytes_uploaded_today,
                 self.destinations)


class Settings(object):
    def __init__(self, sender_settings_list, stored_files_settings):
        self.tmp_file_parts_basepath = stored_files_settings.tmp_file_parts_basepath
        self.should_split_small_files = stored_files_settings.should_split_small_files
        self.sender_specs = []

        for sender_settings in sender_settings_list:
            self.sender_specs.append(_SenderSpec(sender_settings))
