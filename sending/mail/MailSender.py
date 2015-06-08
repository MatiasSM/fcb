import smtplib, os
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email import Encoders
from utils.log_helper import get_logger_module
import time
from random import randint
from time import sleep


class MailSender(object):
    def __init__(self, mail_conf):
        self.log = get_logger_module(self.__class__.__name__)
        self._mail_conf = mail_conf

    def send(self, block):
        """Expects Compressor Block like objects"""
        if self.send_mail(subject=block.ciphered_file_info.basename,
                          text=self._gen_mail_content(block),
                          files=[block.ciphered_file_info.path]):
            if not hasattr(block, 'send_destinations'):
                block.send_destinations = []
            block.send_destinations.extend(self._mail_conf.dst_mail)
            return True
        return False

    def close(self):
        pass

    @staticmethod
    def _gen_file_info(file_info):
        return "File: %s (sha1: %s)\n" % (file_info.basename, file_info.sha1)

    def _gen_mail_content(self, block):
        encrypted = ""
        if hasattr(block, 'ciphered_file_info'):
            encrypted = "* Attached:\n%s" % self._gen_file_info(block.ciphered_file_info)

        return "\n".join(("* Content:",
                          "".join([self._gen_file_info(f) for f in block.content_file_infos]),
                          "* Tar:",
                          self._gen_file_info(block.processed_data_file_info),
                          encrypted
                          ))

    def send_mail(self, subject, text, files):
        assert type(files) == list

        send_from = self._mail_conf.src_mail
        send_to = self._mail_conf.dst_mail

        self.log.debug("Sending to '%s' files '%s'" % (str(send_to), str(files)))
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
                if self._mail_conf.use_ssl:
                    smtp = smtplib.SMTP_SSL(self._mail_conf.mail_server, self._mail_conf.mail_server_port)
                else:
                    smtp = smtplib.SMTP(self._mail_conf.mail_server, self._mail_conf.mail_server_port)
                if self._mail_conf.src_user and self._mail_conf.src_password:
                    smtp.login(self._mail_conf.src_user, self._mail_conf.src_password)
                smtp.sendmail(send_from, send_to, msg.as_string())
                sent = True
            except Exception, e:
                self.log.error("Failed to send '%s' to '%s' try %d of %d. %sError: %s"
                               % (str(files), str(send_to), try_num + 1, self._mail_conf.retries + 1,
                                  "Will retry in %d seconds. " % self._mail_conf.time_between_retries
                                  if try_num < self._mail_conf.retries else "",
                                  str(e)))
                time.sleep(self._mail_conf.time_between_retries)
            if smtp:
                smtp.close()
            if sent:
                break

        sleep(randint(10, 60))  # TODO borrar

        return sent
