from copy import deepcopy
import smtplib
import os
from email import Encoders
import time

from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from fcb.framework.workflow.SenderTask import SenderTask, SendingError


class MailSender(SenderTask):
    def __init__(self, mail_conf):
        SenderTask.__init__(self)
        self._mail_conf = deepcopy(mail_conf)

    def do_send(self, block):
        sending_succedded = self._send_mail(subject=block.latest_file_info.basename,
                                            text=self._gen_mail_content(block),
                                            files=[block.latest_file_info.path])
        if not sending_succedded:
            raise SendingError()

    def destinations(self):
        return self._mail_conf.dst_mails

    @staticmethod
    def _gen_file_info(file_info):
        return "File: {} (sha1: {})\n".format(file_info.basename, file_info.sha1)

    def _gen_mail_content(self, block):
        attached = "* Attached:\n%s" % self._gen_file_info(block.latest_file_info)

        return "\n".join(("* Content:",
                          "".join([self._gen_file_info(f) for f in block.content_file_infos]),
                          "* Tar:",
                          self._gen_file_info(block.processed_data_file_info),
                          attached
                          ))

    def _send_mail(self, subject, text, files):
        assert type(files) == list

        send_from = self._mail_conf.src.mail
        send_to = self._mail_conf.dst_mails

        self.log.debug("Sending to '%s' files '%s'", str(send_to), str(files))
        msg = MIMEMultipart()
        msg['From'] = send_from
        msg['To'] = COMMASPACE.join(send_to)
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = self._mail_conf.subject_prefix + subject

        msg.attach(MIMEText(text))

        for f in files:
            part = MIMEBase('application', "octet-stream")
            part.set_payload(open(f, "rb").read())
            Encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(f))
            msg.attach(part)

        sent = False
        for try_num in range(self._mail_conf.retries + 1):
            smtp = None
            try:
                if self._mail_conf.src.use_ssl:
                    smtp = smtplib.SMTP_SSL(self._mail_conf.src.server, self._mail_conf.src.server_port)
                else:
                    smtp = smtplib.SMTP(self._mail_conf.src.server, self._mail_conf.src.server_port)
                if self._mail_conf.src.user and self._mail_conf.src.password:
                    smtp.login(self._mail_conf.src.user, self._mail_conf.src.password)
                smtp.sendmail(send_from, send_to, msg.as_string())
                sent = True
            except Exception:
                self.log.exception(
                    "Failed to send '%s' to '%s' try %d of %d. %s",
                    str(files),
                    str(send_to),
                    try_num + 1,
                    self._mail_conf.retries + 1,
                    ("Will retry in %d seconds. " % self._mail_conf.time_between_retries
                     if try_num < self._mail_conf.retries else ""))
                time.sleep(self._mail_conf.time_between_retries)
            if smtp:
                smtp.close()
            if sent:
                break
        return sent
