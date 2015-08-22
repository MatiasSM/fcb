from circuits import BaseComponent, handler

from fcb.framework.Marker import Marks
from fcb.framework.events import FilteredFile, PathConsumed, Mark, FileConsumed, NewContainerFile
from fcb.utils.log_helper import get_logger_module


class WorkRateController(BaseComponent):
    _max_pending_for_processing = 0
    _cur_available = 0
    log = None

    def init(self, max_pending_for_processing):
        self.log = get_logger_module(self.__class__.__name__)
        self._max_pending_for_processing = max_pending_for_processing
        self._cur_available = self._max_pending_for_processing

    def try_acquire_slot(self):
        if self._max_pending_for_processing == 0:
            return True
        elif self._cur_available > 0:
            self.slot_taken()
            return True
        return False

    def slot_taken(self):
        self._cur_available -= 1

    def free_slot(self):
        if self._max_pending_for_processing != 0:
            self._cur_available += 1
        self.log.debug("FREE SLOT: %d", self._cur_available)  #TODO BORRAME

    @handler(FilteredFile.__name__)
    def _on_filtered_file(self, *_):
        self.free_slot()

    @handler(Mark.__name__)
    def _on_marker_event(self, mark, *_):
        self.log.debug("EVENTO MARK: %s", mark)  #TODO BORRAME
        if mark == Marks.end_of_pipeline:
            self.free_slot()

    @handler(PathConsumed.__name__)
    def _on_filtered_path(self, *_):
        self.free_slot()

    @handler(FileConsumed.__name__)
    def _on_file_consumed(self, *_):
        self.free_slot()

    @handler(NewContainerFile.__name__)
    def _on_new_container(self, *_):
        self.slot_taken()

