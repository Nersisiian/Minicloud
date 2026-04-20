class MiniCloudError(Exception):
    """Base exception for MiniCloud."""
    pass


class ResourceNotFoundError(MiniCloudError):
    pass


class QuotaExceededError(MiniCloudError):
    pass


class LibvirtOperationError(MiniCloudError):
    pass


class TaskFailureError(MiniCloudError):
    pass