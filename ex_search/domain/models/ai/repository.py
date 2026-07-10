from abc import ABC, abstractmethod
from .ailog import (
    ParserGenerationLog,
    DownloadConfigGenerationLog,
    CodeValidationErrors,
)
from .command import ParserGenerationLogGetCommand, CodeValidationErrorsGetCommand


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


class ICodeValidationErrorsRepository(ABC):
    @abstractmethod
    async def save(self, log_entry: CodeValidationErrors):
        pass

    @abstractmethod
    async def get(
        self, command: CodeValidationErrorsGetCommand
    ) -> list[CodeValidationErrors]:
        pass
