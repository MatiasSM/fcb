from circuits import BaseComponent, handler
from sqlalchemy.orm.exc import NoResultFound
from fcb.database.helpers import get_session
from fcb.database.schema import UploadedPaths
from fcb.framework import events
from fcb.utils.log_helper import get_logger_for


class PathFilter(BaseComponent):
    """
    Filters input paths by checking if it is registered as already processed
    Warning: this will filter files with the same name and path
    """
    log = None
    _session_resource = None

    def init(self):
        self.log = get_logger_for(self)
        self._session_resource = get_session()

    @handler(events.FileProcessed.__name__)
    def on_block_processed(self, block):
        paths = []
        for file_info in block.content_file_infos:
            if hasattr(file_info, 'fragment_info'):  # check if it is a fragment
                if file_info.fragment_info.fragment_num == file_info.fragment_info.fragments_count:
                    # is last fragment
                    paths.append(file_info.upath)
            else:
                paths.append(file_info.upath)  # not a fragmented file
        self._add_paths(paths)

    @handler(events.FileInfoAlreadyProcessed.__name__)
    def on_file_info_processed(self, file_info):
        self._add_paths([file_info.upath])

    @handler(events.NewInputPath.__name__, priority=10)
    def on_input_path(self, event, path):
        path = path.decode("utf-8")
        try:
            with self._session_resource as session:
                session \
                    .query(UploadedPaths) \
                    .filter(UploadedPaths.path == path) \
                    .one()
            self.log.debug("Path already processed: %s", path)
            event.stop()
        except NoResultFound:
            pass

    def _add_paths(self, paths):
        with self._session_resource as session:
            for path in paths:
                session.merge(UploadedPaths(path=path))
