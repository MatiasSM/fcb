
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import settings
from database.schema import ProgramInformation

engine = create_engine(settings.Definitions.connect_string)
Session = sessionmaker(bind=engine)

def create_connection():
    return Session()


def get_session():
    return Session()


def get_db_version(conn):
    """
    :param conn: actually it is a sqlalchemy session
    :return: version number
    """
    value = conn.query(ProgramInformation.value).filter(ProgramInformation.name == "db_version").scalar()
    return int(value)

