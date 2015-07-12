import sys

from fcb.database.helpers import get_session
from fcb.database.schema import FilesContainer
from fcb.processing.transformations.Cipher import Cipher
from fcb.processing.transformations import ToImage
from fcb.utils.digest import gen_sha1
from fcb.utils.log_helper import get_logger_module


# noinspection PyUnresolvedReferences
import log_configuration

log = get_logger_module('untransform_file')


def decrypt(in_filename, out_filename, cipher_key_getter):
    key = cipher_key_getter()
    if key is None:
        log.error("No key to decrypt file '%s', will ignore it", in_filename)
    log.debug("Decrypting file '%s' with key '%s'. Resulting file will be called '%s'." %
              (in_filename, key, out_filename))
    Cipher.decrypt_file(key=key, in_filename=in_filename, out_filename=out_filename)
    log.info("File '%s' decrypted to '%s'." % (in_filename, out_filename))


def transform_from_image(in_filename, out_filename):
    ToImage.from_image_to_file(in_filename, out_filename)


def untransform(in_filename, cipher_key_getter):
    to_process_filename = in_filename
    if ToImage.ToImage.is_transformed(in_filename):
        dst_filename = to_process_filename[:-len(ToImage.ToImage.get_extension())]
        transform_from_image(to_process_filename, dst_filename)
        to_process_filename = dst_filename
    if Cipher.is_transformed(to_process_filename):
        dst_filename = to_process_filename[:-len(Cipher.get_extension())]
        decrypt(to_process_filename, dst_filename, cipher_key_getter)


def _get_key_from_db(session, file_path):
    sha1 = gen_sha1(file_path)
    return session.query(FilesContainer.encryption_key).filter(FilesContainer.sha1 == sha1).scalar()


def untransform_from_db(files):
    with get_session() as session:
        for file_path in files:
            cipher_key_getter = lambda: _get_key_from_db(session, file_path)
            untransform(in_filename=file_path, cipher_key_getter=cipher_key_getter)
        session.close()


def print_usage_and_exit():
    print "Usage:"
    print "\t%s <transformed file> <cipher key>" % sys.argv[0]
    print "\t%s -b <transformed file> [<transformed file> ...]" % sys.argv[0]
    exit(1)


def main():
    if len(sys.argv) < 3 or (len(sys.argv) < 4 and not sys.argv[1] == "-b"):
        print_usage_and_exit()

    if sys.argv[1] == "-b":
        log.debug("Batch mode detected")
        untransform_from_db(sys.argv[2:])
    else:
        log.debug("Single file mode detected")
        untransform(in_filename=sys.argv[1], cipher_key_getter=lambda: sys.argv[3])

if __name__ == '__main__':
    main()
