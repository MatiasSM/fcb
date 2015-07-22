from dateutil import tz
from sqlalchemy.orm.exc import NoResultFound

from fcb.database.helpers import get_session
from fcb.database.schema import UploadedFile
from fcb.framework.workflow.PipelineTask import PipelineTask


class AlreadyProcessedFilter(PipelineTask):
    _session_resource = None

    # override from PipelineTask
    def process_data(self, file_info):
        """expects FileInfo"""
        if self._is_already_processed(file_info):
            self.log.debug("Content file already processed '%s'", str(file_info))
        else:
            return file_info
        return None

    # override from PipelineTask
    def on_stopped(self):
        if self._session_resource:
            with self._session_resource as session:
                session.commit()
                session.close()

    # override from PipelineTask
    def on_start(self):
        if not self._session_resource:
            self._session_resource = get_session()

    # -------- low visibility methods
    def _is_already_processed(self, file_info):
        try:
            with self._session_resource as session:
                uploaded_file = session \
                    .query(UploadedFile) \
                    .filter(UploadedFile.sha1 == file_info.sha1) \
                    .order_by(UploadedFile.upload_date.desc()).one()

            self.log.debug("Found uploaded file by hash: {}".format(uploaded_file))
            # get the uploaded date in local time (FIXME really ugly code)
            date_string = uploaded_file.upload_date.replace(tzinfo=tz.gettz('GMT')).astimezone(tz.tzlocal()).isoformat()

            if uploaded_file.fragment_count > 0:
                # check if all fragments have been uploaded
                if len(uploaded_file.fragments) < uploaded_file.fragment_count:
                    self.log.info(
                        "File '%s' was already started to be uploaded on '%s' but only %d of %d fragments arrived"
                        " to its end, the file will need to be re-uploaded",
                        file_info.path, date_string, len(uploaded_file.fragments), uploaded_file.fragment_count)
                    return False
            self.log.info("File '%s' was already uploaded on '%s' with the name '%s' (sha1 '%s')",
                          file_info.path, date_string, uploaded_file.file_name.encode("utf-8"), str(file_info.sha1))
            return True
        except NoResultFound:
            self.log.debug("No file found for file info: {}".format(file_info))
            return False
