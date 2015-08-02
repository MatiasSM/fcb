from email import parser
import email
import os
import poplib
import re
import tempfile
import time

from sqlalchemy import update, and_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import select

from fcb.database.helpers import get_session
from fcb.database.schema import FilesContainer, CheckerState, Destination, FilesDestinations
from fcb.processing.models.FileInfo import FileInfo
from fcb.utils.log_helper import get_logger_for, get_logger_module

log = get_logger_module('mail_checker')


# FIXME optimize
class CheckHistoryVerifier(object):
    def __init__(self, mail_dst):
        self._session_resource = get_session()
        self._log = get_logger_for(self)
        self._mail_dst = mail_dst
        self._last_checked_date = None

    def close(self):
        if self._session_resource:
            with self._session_resource as session:
                session.commit()
                session.close()

    def _get_last_checked_date(self):
        mail_dst = self._mail_dst
        if not self._last_checked_date:
            value = 0.0
            with self._session_resource as session:
                try:
                    result = session \
                        .query(CheckerState.last_checked_time) \
                        .join(Destination) \
                        .filter(Destination.destination == mail_dst) \
                        .one()
                    value = float(result.last_checked_time)
                except NoResultFound:  # no last checked entry
                    destination = Destination.get_or_add(session, mail_dst)
                    session.flush()  # gen id if necessary
                    session.add(CheckerState(destinations_id=destination.id, last_checked_time=0))
                self._last_checked_date = value
        return self._last_checked_date

    def is_already_checked(self, msg_info):
        last_verif_date = self._get_last_checked_date()
        self._log.debug("last_verif_date '%0.4f', msg_info.msg_date '%0.4f'", last_verif_date, msg_info.msg_date)
        if last_verif_date == msg_info.msg_date:
            self._log.debug("Need to check for message id, last checked time matches the one of the message")
            # because the resolution of the date may not be enough, we need to check by msg id
            try:
                with self._session_resource as session:
                    session \
                        .query(FilesDestinations) \
                        .join(Destination) \
                        .filter(FilesDestinations.verification_info == msg_info.msg_id) \
                        .one()
                return True
            except NoResultFound:
                return False
        else:
            return last_verif_date > msg_info.msg_date

    def set_verified(self, msg_info):
        """
            expects "msg_info" to have the field 'files_containers_id'

            This call already executes "update_last_checked_time" so it doesn't need to be called separately
        """
        assert hasattr(msg_info, 'files_containers_id')
        with self._session_resource as session:
            session.execute(
                update(FilesDestinations)
                    .where(FilesDestinations.file_containers_id == msg_info.files_containers_id)
                    .values(verification_info=msg_info.msg_id)
            )

        self.update_last_checked_time(msg_info)

    def update_last_checked_time(self, msg_info):
        mail_dst = self._mail_dst
        with self._session_resource as session:
            session.execute(
                update(CheckerState)
                    .where(and_(CheckerState.last_checked_time < msg_info.msg_date,
                                CheckerState.destinations_id == select([Destination.id]).
                                where(Destination.destination == mail_dst).
                                as_scalar()))
                    .values(last_checked_time=msg_info.msg_date)
            )


class Checker(object):
    def __init__(self):
        self._session_resource = None
        self._log = get_logger_for(self)

        file_lines = "(^File: .+\\(sha1: .*\\).*\n)+"
        empty_lines = "^(?:\n|\r\n?)*"
        self.is_content_from_fcb_regex = re.compile(''.join((
            '^\* Content:.*\n',
            file_lines,
            empty_lines,
            '^\* Tar:.*\n',
            file_lines,
            empty_lines,
            '^\* Attached:.*\n',
            file_lines
        )), re.MULTILINE)

    def close(self):
        if self._session_resource:
            with self._session_resource as session:
                session.commit()
                session.close()

    def _is_content_from_fcb(self, content):
        return self.is_content_from_fcb_regex.match(content) is not None

    @staticmethod
    def _get_attachment_name(part):
        dtypes = part.get_params(None, 'Content-Disposition')
        if not dtypes:
            if part.get_content_type() == 'text/plain':
                return None
            ctypes = part.get_params()
            if not ctypes:
                return None
            for key, val in ctypes:
                if key.lower() == 'name':
                    print "Attachment (NO DTYPE): '%s'" % val
                    return val
            else:
                return None
        else:
            attachment, filename = None, None
            for key, val in dtypes:
                key = key.lower()
                if key == 'filename':
                    filename = val
                if key == 'attachment':
                    attachment = 1
            if not attachment:
                return None
            print "Attachment: '%s'" % filename
            return filename

    def _get_files_container_by_name(self, file_name):
        if not self._session_resource:
            self._session_resource = get_session()

        try:
            with self._session_resource as session:
                return session \
                    .query(FilesContainer) \
                    .filter(FilesContainer.file_name == file_name) \
                    .one()
        except NoResultFound:
            return None

    def is_uploaded_container(self, msg_info):
        """
            returns 0 if it doesn't correspond to an uploaded container
                   -1 if it corresponds to an uploaded container but it is corrupted
                    1 if it corresponds to an uploaded container and is OK
        """
        results = {
            'BAD': -1,
            'NOT_FCB': 0,
            'OK': 1
        }

        for part in msg_info.msg_body.walk():
            if part.is_multipart():
                continue

            """
            if part.get('Content-Disposition') is None:
                print("no content dispo")
                continue
            """
            if part.get_content_type() == 'text/plain':
                if self._is_content_from_fcb(part.get_payload()):
                    self._log.debug("Body detected as FCB: %s", part.get_payload())
                else:
                    self._log.debug("Body doesn't match FCB: %s", part.get_payload())
                    continue

            attachment_name = self._get_attachment_name(part)
            if not attachment_name:
                self._log.debug("Couldn't get attachment name. Will ignore the part.")
                continue

            files_container = self._get_files_container_by_name(attachment_name)
            if files_container:
                sha1_in_db = files_container.sha1
                msg_info.files_containers_id = files_container.id
                tmp_file = FileInfo(os.path.join(tempfile.gettempdir(), "downloaded.tmp"))
                fp = open(tmp_file.path, 'wb')
                fp.write(part.get_payload(decode=1))
                fp.flush()
                fp.close()

                if tmp_file.sha1 == sha1_in_db:
                    self._log.info("File container '%s' verified!", attachment_name)
                    result = results['OK']
                else:
                    self._log.error("File container '%s' doesn't match the sha1 sum. Expected '%s' but got '%s'",
                                    attachment_name, sha1_in_db, tmp_file.sha1)
                    result = results['BAD']
                os.remove(tmp_file.path)
                return result
            else:
                self._log.debug("Attached file '%s' not found in DB. Will ignore this mail.", attachment_name)
        return results['NOT_FCB']  # otherwise it would have already returned


class MsgInfo(object):
    may_be_fcb_regex = re.compile('archive_.*\\.tar\\.bz2.*')

    def __init__(self, lines):
        expected_fields = 3
        self.msg_date = None
        self.msg_id = None
        self.msg_subject = None
        self.msg_body = None
        for line in lines:
            if line.startswith("Date"):
                sdate = line[6:]
                log.debug("Date: %s", sdate)
                parsed_date = email.utils.parsedate(sdate)
                if parsed_date:
                    self.msg_date = time.mktime(parsed_date)
                    log.debug("Date in time: %f", self.msg_date)
                expected_fields -= 1
            elif line.startswith("Message-ID"):
                self.msg_id = line[12:]
                log.debug("Msg ID: %s", self.msg_id)
                expected_fields -= 1
            elif line.startswith("Subject"):
                self.msg_subject = line[9:]
                log.debug("Subject: %s", self.msg_subject)
                expected_fields -= 1

            if expected_fields == 0:
                break
        if expected_fields > 0:
            raise ValueError("Not all expected fields could be found. Msg: %s" % '\n'.join(
                lines))  # FIXME maybe a more specific error?

        self.msg_body = parser.Parser().parsestr("\n".join(lines))

    def may_be_fcb(self):
        """Tells if the associated message may be from FCB """
        return self.may_be_fcb_regex.match(self.msg_subject) is not None


class Verifier(object):
    def __init__(self):
        self.checker = Checker()
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def close(self):
        self.checker.close()

    def verify(self, mail_conf):
        verifier = CheckHistoryVerifier(mail_conf.user)
        log.debug("Connecting to '%s' using USR '%s' and PASS '%s'",
                  mail_conf.mail_server, mail_conf.user, mail_conf.password)

        pop_conn = poplib.POP3_SSL(mail_conf.mail_server)
        pop_conn.user(mail_conf.user)
        pop_conn.pass_(mail_conf.password)
        # Get messages info from server
        (num_msgs, _) = pop_conn.stat()  # (num_msgs, totalSize)

        log.info("Available messages: %d", num_msgs)

        to_process = []
        # check which is the newest message processed
        for i in range(num_msgs, 0, -1):
            if self._should_stop:
                break
            try:
                log.debug("Getting header of message  %d", i)
                # FIXME should be a better way of checkig or at least take advantage of already downloaded info
                (_, body, _) = pop_conn.top(i, 0)  # (server_msg, body, octets)
                log.debug("Checking if already processed...")
                msg_info = MsgInfo(body)
                if msg_info.may_be_fcb():
                    if verifier.is_already_checked(msg_info):
                        log.debug("Message %d already verified", i)
                        # we found the first message already verified, the remaining should also be already verified
                        break
                    else:
                        log.debug("Message %d NOT verified yet", i)
                        to_process.append(i)
            except Exception as e:
                log.error("Error while processing message %d. Error: %s", i, str(e), exc_info=1)

                # process the messages in reversed order (older first)
        to_process = reversed(to_process)
        for i in to_process:
            if self._should_stop:
                break
            try:
                log.debug("Getting message  %d", i)
                (_, body, _) = pop_conn.retr(i)  # (server_msg, body, octets)
                log.debug("Parsing...")
                msg_info = MsgInfo(body)
                log.debug("Checking...")
                check_result = self.checker.is_uploaded_container(msg_info)

                if check_result > 0:
                    verifier.set_verified(msg_info)
                else:
                    verifier.update_last_checked_time(msg_info)
                log.info("Checked message %d" % i)
            except Exception as e:
                log.error("Error while processing message %d. Error: %s", i, str(e), exc_info=1)
        try:
            pop_conn.quit()
        except Exception as e:
            log.error("Error while trying to close mail connection. Error: %s", str(e), exc_info=1)

        verifier.close()
