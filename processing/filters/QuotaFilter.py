
from framework.workflow.PipelineTask import PipelineTask

class QuotaFilter(PipelineTask):

    def __init__(self, global_quota):
        PipelineTask.__init__(self)
        self._quota = global_quota

    # override from PipelineTask
    def process_data(self, file_info):
        """expects FileInfo"""
        if self._fits_in_quota(file_info):
            return file_info
        else:
            self.log.debug("File would exceed quota. Won't process '%s'", str(file_info))
        return None

    def _fits_in_quota(self, file_info):
        return self._quota.fits(file_info)
