from sqlalchemy import update

from fcb.database.helpers import get_session
from fcb.database.schema import FilesContainer, Destination, FilesDestinations
from fcb.sending.mega.helpers import MegaAccountHandler
from fcb.utils.log_helper import get_logger_for


class _ExternalResourcesHandler(object):
    def __init__(self, mega_dst):
        self._session_resource = get_session()
        self._log = get_logger_for(self)
        self._mega_dst = mega_dst
        self._last_checked_date = None

    def close(self):
        if self._session_resource:
            with self._session_resource as session:
                session.commit()
                session.close()

    def get_unverified_list_from_db(self):
        with self._session_resource as session:
            q = session.query(FilesDestinations.file_containers_id, FilesContainer.file_name) \
                .join(FilesContainer) \
                .join(Destination) \
                .filter(Destination.destination == ("mega: " + self._mega_dst),  # FIXME dependent on cur impl
                        FilesDestinations.verification_info.is_(None))
            return q.all()

    @staticmethod
    def get_unverified_list_from_mega(settings):
        dst_path = MegaAccountHandler.to_absoulte_dst_path(settings) + "/"
        dst_path_pattern = dst_path + "archive_"  # FIXME dependent on cur impl
        cmd = MegaAccountHandler.build_command_argumetns(command_str="megals", settings=settings)
        popen = MegaAccountHandler.execute_command(cmd)
        with popen as proc:
            return [file_name[len(dst_path):].strip()
                    for file_name in proc.stdout
                    if file_name.startswith(dst_path_pattern)]

    def set_verified(self, container_id_set):
        with self._session_resource as session:
            q = update(FilesDestinations) \
                .where(FilesDestinations.file_containers_id.in_(container_id_set)) \
                .values(verification_info="Verified")
            session.execute(q)


class Verifier(object):
    def __init__(self):
        self._should_stop = False
        self._log = get_logger_for(self)

    def stop(self):
        self._should_stop = True

    def close(self):
        pass

    def verify(self, mega_conf):
        class DbEntry:
            def __init__(self, db_entry):
                self.db_entry = db_entry

            def __eq__(self, other):
                if isinstance(other, DbEntry):
                    return self.db_entry.file_name == other.db_entry.file_name
                else:
                    return self.db_entry.file_name == other

            def __hash__(self):
                return hash(self.db_entry.file_name)

            def __str__(self):
                return "fn: {} --- id: {}".format(self.db_entry.file_name, self.db_entry.file_containers_id)

        ext_res_handler = _ExternalResourcesHandler(mega_dst=mega_conf.user)
        db_list = set((DbEntry(db_entry) for db_entry in ext_res_handler.get_unverified_list_from_db()))
        if db_list:
            uploaded_file_list = set(ext_res_handler.get_unverified_list_from_mega(mega_conf))
            db_list.intersection_update(uploaded_file_list)
            if db_list:
                ext_res_handler.set_verified([item.db_entry.file_containers_id for item in db_list])
        ext_res_handler.close()

