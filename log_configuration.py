
import logging
import sys

logger = logging.getLogger('fcb') #logger for files_cloud_backuper
formatter = logging.Formatter('[%(levelname)s][%(asctime)s][%(thread)d][%(name)s] %(message)s')

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
logger.addHandler(ch) 

logger.setLevel(logging.DEBUG)
