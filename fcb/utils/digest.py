import hashlib
from functools import partial


def gen_sha1(file_path):
    with open(file_path, mode='rb') as f:
        d = hashlib.sha1()
        #TODO make the amount of bytes of buffer (128) configurable
        for buf in iter(partial(f.read, 128), b''):
            d.update(buf)
    return d.hexdigest()       