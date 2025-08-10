from enum import auto
from common.enums import AutoUpperName


class UpdateStatus(AutoUpperName):
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    COMPLETED_WITH_ERRORS = auto()
    FAILED = auto()
    CANCELED = auto()
    UNKNOWN = auto()
