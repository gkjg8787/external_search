from enum import Enum, auto
from common.enums import AutoLowerName


class SuppoertedDomain(Enum):
    SOFMAP = "www.sofmap.com"
    A_SOFMAP = "a.sofmap.com"


class SupportedSiteName(AutoLowerName):
    SOFMAP = auto()


class ActivityName(Enum):
    SearchClient = auto()
    SearchInfo = auto()


class URLDomainStatus(AutoLowerName):
    DOWNLOADING = auto()
    COMPLETED = auto()
    FAILED = auto()


class InfoName(AutoLowerName):
    CATEGORY = auto()
