from abc import ABC, abstractmethod
from .ailog import ParserGenerationLog
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
