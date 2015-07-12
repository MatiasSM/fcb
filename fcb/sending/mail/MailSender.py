from copy import deepcopy
import smtplib
import os
from email import Encoders
import time

from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate

from fcb.framework.workflow.PipelineTask import PipelineTask


class MailSender(PipelineTask):
    def __init__(self, mail_conf):
        PipelineTask.__init__(self)
        self._mail_conf = deepcopy(mail_conf)

    # override from PipelineTask
    def process_data(self, block):
        """
        Note: Expects Compressor Block like objects
        """
        ''' FIXME currently we return block whether it was correctly processed or not because MailSenders are chained
            and not doing that would mean other wouldn't be able to try.'''
        if not set(self._mail_conf.dst_mails).issubset(block.destinations):
            self.log.debug("Block not for this mail destination %s", self._mail_conf.dst_mails)
            return block

        if self._send_mail(subject=block.latest_file_info.basename,
                           text=self._gen_mail_content(block),
                           files=[block.latest_file_info.path]):
            if not hasattr(block, 'send_destinations'):
                block.send_destinations = []
            block.send_destinations.extend(self._mail_conf.dst_mails)
        return block
        # return None

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
            except Exception, e:
                self.log.error("Failed to send '%s' to '%s' try %d of %d. %sError: %s",
                               str(files), str(send_to), try_num + 1, self._mail_conf.retries + 1,
                               ("Will retry in %d seconds. " % self._mail_conf.time_between_retries
                                if try_num < self._mail_conf.retries else ""),
                               str(e))
                time.sleep(self._mail_conf.time_between_retries)
            if smtp:
                smtp.close()
            if sent:
                break
        return sent