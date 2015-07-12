import datetime

from sqlalchemy import Column, DateTime, String, Integer, Float, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.sqltypes import UnicodeText

from fcb.database import settings

Base = declarative_base()


class ProgramInformation(Base):
    """
    Holds metadata information for the program and DB
    """
    __tablename__ = 'program_information'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    value = Column(String)
    modification_date = Column(DateTime, default=datetime.datetime.utcnow())


class UploadedFile(Base):
    """
    Information about files that have been uploaded
    """
    __tablename__ = 'uploaded_files'
    id = Column(Integer, primary_key=True)
    sha1 = Column(String)
    file_name = Column(UnicodeText)
    fragment_count = Column(Integer)
    upload_date = Column(DateTime, default=datetime.datetime.utcnow())


class Destination(Base):
    """
    cloud storage destinations
    """
    __tablename__ = 'destinations'
    id = Column(Integer, primary_key=True)
    destination = Column(String)  # destination name
    creation_date = Column(DateTime, default=datetime.datetime.utcnow())  # date when the destination was created

    @classmethod
    def get_or_add(cls, a_session, destination):
        try:
            return a_session.query(cls).filter(cls.destination == destination).one()
        except NoResultFound:
            new_instance = cls(destination=destination)
            a_session.add(new_instance)
            return new_instance

class FilesContainer(Base):
    """
    Information about file containers files
    """
    __tablename__ = 'files_containers'
    id = Column(Integer, primary_key=True)
    sha1 = Column(String)  # SHA1 of the file container
    file_name = Column(String)  # name of the container file
    encryption_key = Column(String)  # key used to encrypt the container
    container_size = Column(Integer)  # container file size
    upload_date = Column(DateTime, default=datetime.datetime.utcnow())  # date when the container file was uploaded

    files_destinations = relationship("FilesDestinations", backref="file_containers")


class FileFragment(Base):
    """
    Information about fragments that compose a file
    """
    __tablename__ = 'file_fragments'
    id = Column(Integer, primary_key=True)
    fragment_sha1 = Column(String)  # SHA1 of the fragment file
    fragment_name = Column(UnicodeText)  # name of the fragment file
    fragment_number = Column(Integer)  # ordinal of the fragment
    upload_date = Column(DateTime, default=datetime.datetime.utcnow())  # date when the container file was uploaded

    file_id = Column(Integer, ForeignKey(UploadedFile.id))
    file = relationship(UploadedFile, backref="fragments")


class FilesDestinations(Base):
    """
    FilesContainer <-> Destination association

    TODO fix FK cascade remove
    """
    __tablename__ = 'files_destinations'
    file_containers_id = Column(Integer, ForeignKey(FilesContainer.id), primary_key=True)
    destinations_id = Column(Integer, ForeignKey(Destination.id), primary_key=True)
    '''
    "verification_info" will hold any information required to indicate that the file reached
    successfully the destination.
    The type of information held depend on the destination type.
    '''
    verification_info = Column(String, nullable=True)

    destination = relationship(Destination, backref="files_destinations")

    @classmethod
    def get_bytes_uploaded_in_date(cls,
                                   a_session,
                                   destinations=None,
                                   date=datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)):
        one_more_day = date + datetime.timedelta(days=1)

        size_sum = a_session\
            .query(func.sum(FilesContainer.container_size))\
            .select_from(FilesDestinations) \
            .join(Destination) \
            .join(FilesContainer) \
            .filter(FilesContainer.upload_date >= date,
                    FilesContainer.upload_date < one_more_day,
                    Destination.destination.in_(destinations) if destinations is not None and destinations else True)\
            .scalar()
        return 0 if size_sum is None else size_sum


class FilesInContainers(Base):
    """
    FilesContainer <-> UploadedFile/Fragments association

    TODO fix FK cascade remove
    """
    __tablename__ = 'files_in_containers'
    file_containers_id = Column(Integer, ForeignKey(FilesContainer.id), primary_key=True)
    uploaded_files_id = Column(Integer, ForeignKey(UploadedFile.id), primary_key=True)
    uploaded_file_fragment_number = Column(Integer, primary_key=True)  # TODO remove/rename

    container_file = relationship(FilesContainer, backref="fragments")
    # TODO a file needs to know which fragments in which containers exists?


class CheckerState(Base):
    """
    upload_checker state information

    TODO fix FK cascade remove
    """
    __tablename__ = 'checker_state'
    id = Column(Integer, primary_key=True)
    destinations_id = Column(Integer, ForeignKey(Destination.id))
    last_checked_time = Column(Float)


def main():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(settings.Definitions.connect_string)
    Base.metadata.create_all(engine)

    # save version information
    Session = sessionmaker(bind=engine)

    session = Session()
    session.add(ProgramInformation(name="db_version", value="3"))

    session.commit()

if __name__ == '__main__':
    main()
