import threading
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fcb.database import settings
from fcb.database.schema import ProgramInformation

_engine = create_engine(settings.Definitions.connect_string)
_Session = sessionmaker(bind=_engine)


class _LockedSession(object):
    """
    This class is used to access database one thread at the time to avoid "database is locked" errors when using SQLite
    Because SQLAlchemy sessions are not thread safe (nor multi-thread shareable seems), we use different sessions
      but share the locks (to ensure exclusive access to DB)
    When/If a different engine is to be used, this class may be changed to avoid locking in that case
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._cur_session = None

    def __enter__(self):
        self._lock.acquire()
        self._cur_session = _Session()
        return self._cur_session

    def __exit__(self, *_):
        self._cur_session.commit()
        self._cur_session.close()
        self._lock.release()


_shared_session = _LockedSession()


def get_session():
    return _shared_session


def get_db_version(session):
    """
    :param session: actually it is a sqlalchemy session
    :return: version number
    """
    value = session.query(ProgramInformation.value).filter(ProgramInformation.name == "db_version").scalar()
    return int(value)
