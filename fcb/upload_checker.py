import signal
import sys

from fcb.checker import mail, mega
from fcb.checker.settings import Configuration
from fcb.database.helpers import get_session
from fcb.database.helpers import get_db_version
from fcb.utils.log_helper import get_logger_module

log = get_logger_module('mail_checker')


def main():
    # noinspection PyUnresolvedReferences
    import log_configuration

    if len(sys.argv) < 2:
        log.error("Usage: %s <config_file>", sys.argv[0])
        exit(1)

    conf = Configuration(sys.argv[1])

    with get_session() as session:
        db_version = get_db_version(session)
        if db_version != 3:
            log.error("Invalid database version (%d). 3 expected", db_version)
            session.close()
            exit(1)

        session.close()

    mail_verifier = mail.Verifier()
    mega_verifier = mega.Verifier()

    def signal_handler(signal, frame):
        print "Abort signal received!!!!"
        mail_verifier.stop()
        mega_verifier.stop()

    signal.signal(signal.SIGINT, signal_handler)

    for mail_conf in conf.mail_confs:
        mail_verifier.verify(mail_conf)

    for meaga_conf in conf.mega_confs:
        mega_verifier.verify(meaga_conf)

    mail_verifier.close()
    mega_verifier.close()

if __name__ == '__main__':
    main()
