from abc import ABC, abstractmethod
from .ailog import ParserGenerationLog, DownloadConfigGenerationLog
from .command import ParserGenerationLogGetCommand


class IParserGenerationLogRepository(ABC):
    @abstractmethod
    async def save_all(self, log_entries: list[ParserGenerationLog]):
        pass

    @abstractmethod
    async def get(
        self, command: ParserGenerationLogGetCommand
    ) -> list[ParserGenerationLog]:
        pass


class IDownloadConfigGenerationLogRepository(ABC):
    @abstractmethod
    async def save(self, log_entry: DownloadConfigGenerationLog):
        pass
