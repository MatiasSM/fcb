from fcb.framework import events
from fcb.framework.workflow.PipelineTask import PipelineTask


class QuotaFilter(PipelineTask):
    _quota = None
    _stop_on_remaining = None

    def do_init(self, global_quota, stop_on_remaining):
        self._quota = global_quota
        self._stop_on_remaining = stop_on_remaining

    # override from PipelineTask
    def process_data(self, file_info):
        """expects FileInfo"""
        if self._has_reached_stop_limit():
            self.log.info("Remaining bytes in quota (%d) has reached minimum to request stop (%d)",
                          self._quota.remaining, self._stop_on_remaining)
            self.fire(events.TransmissionQuotaReached())
        elif not self._fits_in_quota(file_info):
            self.log.debug("File would exceed quota. Won't process '%s'", str(file_info))
        else:
            return file_info

    def _fits_in_quota(self, file_info):
        return self._quota.fits(file_info)

    def _has_reached_stop_limit(self):
        return not self._quota.is_infinite() and self._quota.remaining <= self._stop_on_remaining
