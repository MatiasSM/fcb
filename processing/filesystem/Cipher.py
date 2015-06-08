'''
Based on code available in http://eli.thegreenplace.net/2010/06/25/aes-encryption-of-files-in-python-with-pycrypto/
'''
import os, string, random, struct
from Crypto.Cipher import AES
from processing.filesystem.File_Info import File_Info
from utils.log_helper import get_logger_module

class Cipher(object):
    def __init__(self, out_queue):
        self.log = get_logger_module(self.__class__.__name__)
        self._out_queue = out_queue

    def encrypt(self, block):
        '''Expects Compressor Block like objects'''
        
        block.cipher_key = Cipher.gen_key(32)
        block.ciphered_file_info = File_Info(block.processed_data_file_info.path + ".enc")
        self.log.debug("Encrypting file '%s' with key '%s' to file '%s'" % 
                       (block.processed_data_file_info.path, block.cipher_key, block.ciphered_file_info.path))
        Cipher.encrypt_file(key=block.cipher_key, 
                            in_filename=block.processed_data_file_info.path, 
                            out_filename=block.ciphered_file_info.path)
        self._out_queue.put(block)

    @classmethod
    def gen_key(cls, size):
        return ''.join(random.choice("".join((string.letters,string.digits,string.punctuation))) for _ in range(size))
    
    @classmethod
    def encrypt_file(cls, key, in_filename, out_filename=None, chunksize=64*1024):
        """ Encrypts a file using AES (CBC mode) with the
            given key.
    
            key:
                The encryption key - a string that must be
                either 16, 24 or 32 bytes long. Longer keys
                are more secure.
    
            in_filename:
                Name of the input file
    
            out_filename:
                If None, '<in_filename>.enc' will be used.
    
            chunksize:
                Sets the size of the chunk which the function
                uses to read and encrypt the file. Larger chunk
                sizes can be faster for some files and machines.
                chunksize must be divisible by 16.
        """
        if not out_filename:
            out_filename = in_filename + '.enc'
    
        iv = ''.join(chr(random.randint(0, 0xFF)) for _ in range(16))
        encryptor = AES.new(key, AES.MODE_CBC, iv)
        filesize = os.path.getsize(in_filename)
    
        with open(in_filename, 'rb') as infile:
            with open(out_filename, 'wb') as outfile:
                outfile.write(struct.pack('<Q', filesize))
                outfile.write(iv)
    
                while True:
                    chunk = infile.read(chunksize)
                    if len(chunk) == 0:
                        break
                    elif len(chunk) % 16 != 0:
                        chunk += ' ' * (16 - len(chunk) % 16)
    
                    outfile.write(encryptor.encrypt(chunk))
                   
    @classmethod                
    def decrypt_file(cls, key, in_filename, out_filename=None, chunksize=24*1024):
        """ Decrypts a file using AES (CBC mode) with the
            given key. Parameters are similar to encrypt_file,
            with one difference: out_filename, if not supplied
            will be in_filename without its last extension
            (i.e. if in_filename is 'aaa.zip.enc' then
            out_filename will be 'aaa.zip')
        """
        if not out_filename:
            out_filename = os.path.splitext(in_filename)[0]
    
        with open(in_filename, 'rb') as infile:
            origsize = struct.unpack('<Q', infile.read(struct.calcsize('Q')))[0]
            iv = infile.read(16)
            decryptor = AES.new(key, AES.MODE_CBC, iv)
    
            with open(out_filename, 'wb') as outfile:
                while True:
                    chunk = infile.read(chunksize)
                    if len(chunk) == 0:
                        break
                    outfile.write(decryptor.decrypt(chunk))
    
                outfile.truncate(origsize)