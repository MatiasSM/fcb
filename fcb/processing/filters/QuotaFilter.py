
from fcb.framework.workflow.PipelineTask import PipelineTask

class QuotaFilter(PipelineTask):

    def __init__(self, global_quota, stop_on_remaining, request_processing_stop_cb):
        PipelineTask.__init__(self)
        self._quota = global_quota
        self._stop_on_remaining = stop_on_remaining
        self._request_processing_stop_cb = request_processing_stop_cb

    # override from PipelineTask
    def process_data(self, file_info):
        """expects FileInfo"""
        if self._has_reached_stop_limit():
            self.log.info("Remaining bytes in quota (%d) has reached minimum to request stop (%d)",
                          self._quota.remaining, self._stop_on_remaining)
            self._request_processing_stop_cb()
        else:
            if self._fits_in_quota(file_info):
                return file_info
            else:
                self.log.debug("File would exceed quota. Won't process '%s'", str(file_info))
        return None

    def _fits_in_quota(self, file_info):
        return self._quota.fits(file_info)

    def _has_reached_stop_limit(self):
        return not self._quota.is_infinite() and self._quota.remaining <= self._stop_on_remaining
