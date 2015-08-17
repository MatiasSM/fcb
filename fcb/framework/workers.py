from circuits import Worker


class _WorkerPool(object):
    """
    Represents an circuits.worker poll
    """
    _register_component = None

    def register_workers(self, app):
        raise NotImplementedError()

    def get_worker(self):
        raise NotImplementedError()


class _HardDriveWorkerPool(_WorkerPool):
    """
    Workers to do I/O to hard drive

    TODO: this can be differentiated by HD device destination
    """
    _worker = None

    def __init__(self):
        super(_HardDriveWorkerPool, self).__init__()
        # TODO let the amount of threads be configurable
        self._worker = Worker(channel=self.__class__.__name__, workers=1)

    def get_worker(self):
        return self._worker

    def register_workers(self, app):
        self._worker.register(app)


class _UncappedInternetUploadWorkerPool(_WorkerPool):
    """
    Worker to upload things to Internet when the destination is uncapped
    """
    _worker = None

    def __init__(self):
        super(_UncappedInternetUploadWorkerPool, self).__init__()
        # TODO let the amount of threads be configurable
        self._worker = Worker(channel=self.__class__.__name__, workers=1)

    def get_worker(self):
        return self._worker

    def register_workers(self, app):
        self._worker.register(app)


class _DefaultWorkerPool(_WorkerPool):
    """
    Worker to use when no more specific is defined
    """
    _worker = None

    def __init__(self):
        super(_DefaultWorkerPool, self).__init__()
        # TODO let the amount of threads be configurable
        self._worker = Worker(channel=self.__class__.__name__, workers=1)

    def get_worker(self):
        return self._worker

    def register_workers(self, app):
        self._worker.register(app)


class _PoolsManager(object):
    _app = None
    _registered_pools = []

    def register_app(self, app):
        for pool in self._registered_pools:
            pool.register_workers(app)

    def add_pool(self, pool):
        if self._app is not None:
            pool.register_workers(self._app)
        self._registered_pools.append(pool)


manager = _PoolsManager()

default_worker_pool = _DefaultWorkerPool()
manager.add_pool(default_worker_pool)

# global resources
hd_worker_pool = _HardDriveWorkerPool()
manager.add_pool(hd_worker_pool)

_uncapped_internet_worker_pool = _UncappedInternetUploadWorkerPool()
manager.add_pool(_uncapped_internet_worker_pool)

# currently all services are assumed as uncapped (thus, they share a worker)
mail_sender_worker_pool = _uncapped_internet_worker_pool
mega_sender_worker_pool = _uncapped_internet_worker_pool
