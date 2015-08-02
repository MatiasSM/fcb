import sys
from fcb.checker.cleanup.helper import delete_unverified_uploads
from fcb.checker.settings import Configuration
from fcb.utils.log_helper import get_logger_module


def main():
    # noinspection PyUnresolvedReferences
    import log_configuration

    log = get_logger_module('db_cleanup')

    if len(sys.argv) < 2:
        log.error("Usage: %s <config_file>", sys.argv[0])
        exit(1)

    conf = Configuration(sys.argv[1])

    destinations = [mail.user for mail in conf.mail_confs] + \
                   [("mega: " + mega.user) for mega in conf.mega_confs]  # FIXME dependent on cur impl

    print "This will delete all records associated to unverified uploads for destinations {}.\n".format(destinations), \
        "This tool should ONLY be run after a complete and successful execution of upload checker,", \
        "otherwise you WILL be loosing unrecoverable information about your uploads."

    try:
        answer = raw_input("Do you want to continue with the execution (y/N)? ")
        if answer and answer in "yY":
            delete_unverified_uploads(destinations)
            log.info("Done")
            return
        else:
            if answer not in "nN":
                print "Unrecognized option '%s'" % answer
    except KeyboardInterrupt:
        pass
    print "Execution aborted"


if __name__ == '__main__':
    main()
