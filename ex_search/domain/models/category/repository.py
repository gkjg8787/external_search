from abc import ABC, abstractmethod

from .category import Category
from .command import CategoryGetCommand


class ICategoryRepository(ABC):

    @abstractmethod
    async def save_all(self, cate_entries: list[Category]):
        pass

    @abstractmethod
    async def get(self, command: CategoryGetCommand) -> list[Category]:
        pass
