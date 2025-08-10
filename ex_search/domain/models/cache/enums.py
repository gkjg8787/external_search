from enum import auto

from common.enums import AutoUpperName


class OrderStatus(AutoUpperName):
    PENDING = auto()
    COMPLETED = auto()
    CANCELLED = auto()
    FAILED = auto()


class DownloadType(AutoUpperName):
    HTTPX = auto()
    SELENIUM = auto()
