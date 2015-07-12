import logging
import sys

level = logging.DEBUG

logger = logging.getLogger('fcb')  # logger for files_cloud_backuper
formatter = logging.Formatter('[%(levelname)s][%(asctime)s][%(thread)d][%(name)s] %(message)s')

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.FileHandler('/tmp/fcb_out_exec.log')
fh.setFormatter(formatter)
logger.addHandler(fh)

logger.setLevel(level)
