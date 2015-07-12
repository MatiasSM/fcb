import threading


class Quota(object):
    """
    Represents an amount of bytes that can be "used"
    It is capable of querying FileInfo (like) instances to compare against this state
    """

    def __init__(self, quota_limit, be_thread_safe=True, used_quota=0):
        """
        :param quota_limit: limit in bytes of the (daily) quota
        :param be_thread_safe: if True, the instance access will be thread safe
        :param used_quota: amount of quota already used (in bytes)
        """
        class FakeLock(object):
            def acquire(self, blocking=True):
                pass

            def release(self):
                pass

        self._lock = threading.Lock() if be_thread_safe else FakeLock()
        self._limit = quota_limit
        self._used = used_quota

    @property
    def used(self):
        return self._used

    @property
    def limit(self):
        """
        :return: the limit in bytes associated to the instance or
                 0 if is_infinite() is True
        """
        return self._limit

    @property
    def remaining(self):
        """
        Note: only meaningful if is_infinite is not True
        """
        return max((0, self.limit - self.used))

    def is_infinite(self):
        return self._limit == 0

    def account_used(self, file_info):
        self._lock.acquire()
        self._unsafe_account_used(file_info)
        self._lock.release()

    def fits(self, file_info):
        self._lock.acquire()
        result = self._unsafe_fits(file_info)
        self._lock.release()
        return result

    def _unsafe_account_used(self, file_info):
        self._used += file_info.size

    def _unsafe_fits(self, file_info):
        return self.is_infinite() or (self._limit - self._used >= file_info.size)
