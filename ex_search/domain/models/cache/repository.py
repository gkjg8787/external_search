from abc import ABC, abstractmethod
from .cache import SearchCache
from .command import SearchCacheGetCommand, SearchCacheDeleteCommand


class ISearchCacheRepository(ABC):
    @abstractmethod
    async def save(self, data: SearchCache):
        pass

    @abstractmethod
    async def get(self, command: SearchCacheGetCommand) -> list[SearchCache]:
        pass


class ISearchCacheDeleteRepository(ABC):
    @abstractmethod
    async def delete_all(self, command: SearchCacheDeleteCommand):
        pass
