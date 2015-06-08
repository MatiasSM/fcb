from dateutil import tz
from sqlalchemy.orm.exc import NoResultFound

from database.helpers import get_session
from database.schema import UploadedFile
from utils.log_helper import get_logger_module


class AlreadyProcessedFilter(object):
    def __init__(self, out_queue):
        self._log = get_logger_module(self.__class__.__name__)
        self._session = None
        self._out_queue = out_queue

    def filter(self, file_info):
        """expects Path_Info"""

        if self._is_already_processed(file_info):
            self._log.debug("Content file already processed '%s'", str(file_info))
        else:
            self._out_queue.put(file_info)

    def finish(self):
        if self._session:
            self._session.commit()
            self._session.close()

    def _is_already_processed(self, file_info):
        if not self._session:
            self._session = get_session()

        try:
            uploaded_file = self._session \
                .query(UploadedFile) \
                .filter(UploadedFile.sha1 == file_info.sha1) \
                .order_by(UploadedFile.upload_date.desc()).one()

            # get the uploaded date in local time (FIXME really ugly code)
            date_string = uploaded_file.upload_date.replace(tzinfo=tz.gettz('GMT')).astimezone(tz.tzlocal()).isoformat()

            if uploaded_file.fragment_count > 0:
                # check if all fragments have been uploaded
                if len(uploaded_file.fragments) < uploaded_file.fragment_count:
                    self._log.info(
                        "File '%s' was already started to be uploaded on '%s' but only %d of %d fragments arrived"
                        " to its end, the file will need to be re-uploaded" %
                        (file_info.path, date_string, len(uploaded_file.fragments), uploaded_file.fragment_count))
                    return False
            self._log.info("File '%s' was already uploaded on '%s' with the name '%s' (sha1 '%s')" %
                           (file_info.path, date_string, uploaded_file.file_name, file_info.sha1))
            return True
        except NoResultFound:
            return False
