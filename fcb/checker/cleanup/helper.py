from sqlalchemy import select
from sqlalchemy.orm.util import aliased
from sqlalchemy.sql.expression import exists, and_

from fcb.database.helpers import get_session
from fcb.database.schema import FilesDestinations, Destination, FileFragment, FilesContainer, FilesInContainers, \
    UploadedFile
from fcb.utils.log_helper import get_logger_module


_log = get_logger_module('cleanup_helper')


def delete_unverified_uploads(destinations):
    """
    :param destinations: list of Destination.destination

    For each Destination.destination:
        Deletes all FilesDestinations where the destination is not verified
        Deletes each FilesContainer in the deleted FilesDestinations if not present in a non deleted FilesDestinations
        Deletes each FileFragment if corresponds to a FilesInContainers for a FilesContainer deleted and not in
            a non deleted FilesContainer
        Deletes each UploadedFile if corresponds to a FilesInContainers for a FilesContainer deleted and not in
            a non deleted FilesContainer and/or has no more FileFragment in non deleted FilesContainer
    """
    with get_session() as session:
        # TODO use triggers or cascades to delete relations
        for destination in destinations:
            _log.info("Deleting unverified uploads for destination %s", destination)

            # get unverified FilesDestinations for the configured mail_conf
            files_destinations_q = session.query(FilesDestinations)\
                .filter(
                    FilesDestinations.verification_info.is_(None),
                    FilesDestinations.destinations_id == (
                        select([Destination.id]).
                        where(Destination.destination == destination).
                        as_scalar()))
            files_destinations = files_destinations_q.all()

            if not files_destinations:
                continue

            # get FilesContainer.id for containers which are not associated to another destination
            fd1 = aliased(FilesDestinations)
            fd2 = aliased(FilesDestinations)
            files_container_ids_to_delete = [
                f.file_containers_id for f in
                session.query(fd1.file_containers_id)
                .filter(fd1.file_containers_id.in_([fd.file_containers_id for fd in files_destinations]))
                .filter(~exists().where(
                    and_(fd1.file_containers_id == fd2.file_containers_id,
                         fd1.destinations_id != fd2.destinations_id)))
                .all()
                ]

            # will delete all FilesInContainers for containers to be deleted. FIXME could be done in cascade
            files_in_container_q = session.query(FilesInContainers)\
                .filter(FilesInContainers.file_containers_id.in_(files_container_ids_to_delete))

            # get files (and fragments) only present in containers to delete (can be deleted also)
            fic1 = aliased(FilesInContainers)
            fic2 = aliased(FilesInContainers)
            files_to_delete = session.query(fic1)\
                .filter(fic1.file_containers_id.in_(files_container_ids_to_delete))\
                .filter(~exists().where(
                    and_(
                        # same file/fragment
                        fic1.uploaded_files_id == fic2.uploaded_files_id,
                        fic1.uploaded_file_fragment_number == fic2.uploaded_file_fragment_number,
                        # in other container
                        ~fic2.file_containers_id.in_(files_container_ids_to_delete)
                    )))\
                .all()

            # delete fragments
            # FIXME needs to be optimized (using placeholders or something)
            for file_id, fragment_number in \
                    [(f.uploaded_files_id, f.uploaded_file_fragment_number)
                     for f in files_to_delete if f.uploaded_file_fragment_number > 0]:
                session.query(FileFragment)\
                    .filter(FileFragment.file_id == file_id, FileFragment.fragment_number == fragment_number)\
                    .delete(synchronize_session='fetch')

            # delete uploaded files without fragments
            whole_file_ids = [f.uploaded_files_id for f in files_to_delete if f.uploaded_file_fragment_number == 0]
            if whole_file_ids:
                session.query(UploadedFile)\
                    .filter(UploadedFile.id.in_(whole_file_ids))\
                    .delete(synchronize_session='fetch')

            # delete uploaded files with all their fragments deleted. FIXME optimize
            fragmented_file_ids = [f.uploaded_files_id for f in files_to_delete if f.uploaded_file_fragment_number > 0]
            if fragmented_file_ids:
                session.query(UploadedFile)\
                    .filter(UploadedFile.id.in_(fragmented_file_ids),
                            ~exists().where(FileFragment.file_id == UploadedFile.id))\
                    .delete(synchronize_session='fetch')

            session.query(FilesContainer)\
                .filter(FilesContainer.id.in_(files_container_ids_to_delete))\
                .delete(synchronize_session='fetch')

            files_in_container_q.delete(synchronize_session='fetch')
            files_destinations_q.delete(synchronize_session='fetch')
        session.commit()
