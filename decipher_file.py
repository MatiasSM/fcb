import sys

from database.helpers import get_session
from database.schema import FilesContainer
from processing.transformations.Cipher import Cipher
from processing.transformations import ToImage
from utils.digest import gen_sha1
from utils.log_helper import get_logger_module


# noinspection PyUnresolvedReferences
import log_configuration

log = get_logger_module('decipher_file')

# TODO renombrar a transform_file
# TODO determinar si esta transformado a imagen y convertirlo previamente
# TODO determinar si esta cifrado y descifrarlo
# TODO remover extensiones (en lugar de agregar nuevas)

def transform_from_image(in_filename, out_filename):
    ToImage.from_image_to_file(in_filename, out_filename)

def decript(key, in_filename, out_filename):
    log.debug("Decrypting file '%s' with key '%s'. Resulting file will be called '%s'." %
              (in_filename, key, out_filename))
    Cipher.decrypt_file(key=key, in_filename=in_filename, out_filename=out_filename)
    log.info("File '%s' decrypted to '%s'." % (in_filename, out_filename))


def decript_from_db(files):
    session = get_session()

    for file_path in files:
        sha1 = gen_sha1(file_path)
        encryption_key = session.query(FilesContainer.encryption_key).filter(FilesContainer.sha1 == sha1).scalar()
        if encryption_key is not None:
            log.debug("Got key '%s' for file '%s' with sha1 '%s'" % (encryption_key, file_path, sha1))
            decript(key=encryption_key, in_filename=file_path, out_filename=file_path + ".dec")
        else:
            log.error("No key found for file '%s' with sha1 '%s'" % (file_path, sha1))
    session.close()


def print_usage_and_exit():
    print "Usage:"
    print "\t%s <encrypted file> <out file> <key>" % sys.argv[0]
    print "\t%s -b <encrypted file> [<encripted file> ...]" % sys.argv[0]
    exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 3 or (len(sys.argv) < 4 and not sys.argv[1] == "-b"):
        print_usage_and_exit()

    if sys.argv[1] == "-b":
        log.debug("Batch mode detected")
        decript_from_db(sys.argv[2:])
    else:
        log.debug("Single file mode detected")
        decript(key=sys.argv[3], in_filename=sys.argv[1], out_filename=sys.argv[2])
