from database.schema import FilesDestinations
from utils.log_helper import get_logger_for

class _SenderRestriction(object):
    def __init__(self, sender_settings):
        self.max_upload_per_day_in_bytes = sender_settings.limits.max_upload_per_day.in_bytes
        self.max_size_in_bytes = sender_settings.limits.max_size.in_bytes

    def __eq__(self, other):
        return other \
               and self.max_upload_per_day_in_bytes == other.max_upload_per_day_in_bytes \
               and self.max_size_in_bytes == other.max_size_in_bytes

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.max_upload_per_day_in_bytes, self.max_size_in_bytes))

class _SenderSpec(object):
    restrictions = None
    destinations = None
    bytes_uploaded_today = 0

    def __init__(self, sender_settings, db_session):
        log = get_logger_for(self)
        self.restrictions = _SenderRestriction(sender_settings)
        self.destinations = sender_settings.destinations
        self.bytes_uploaded_today = \
            FilesDestinations.get_bytes_uploaded_in_date(db_session, self.destinations)
        log.info("According to the logs, it were already uploaded today %d bytes for destinations %s",
                 self.bytes_uploaded_today,
                 self.destinations)


class Settings(object):
    def __init__(self, sender_settings_list, stored_files_settings, db_session):
        self.tmp_file_parts_basepath = stored_files_settings.tmp_file_parts_basepath
        self.should_split_small_files = stored_files_settings.should_split_small_files
        self.sender_specs = []

        for sender_settings in sender_settings_list:
            self.sender_specs.append(_SenderSpec(sender_settings, db_session))
