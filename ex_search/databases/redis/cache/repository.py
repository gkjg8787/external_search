import json
import uuid

import redis.asyncio as aredis

from domain.models.cache import cache, command, repository


class SearchCacheRedisRepository(repository.ISearchCacheRepository):
    HEADER = "URL:"
    r: aredis.Redis
    expiry_seconds: int

    def __init__(self, r: aredis.Redis, expiry_seconds: int | None = None):
        self.r = r
        if expiry_seconds:
            self.expiry_seconds = expiry_seconds
        else:
            self.expiry_seconds = 3600

    async def save(self, data: cache.SearchCache):
        if not data.id:
            data.id = uuid.uuid4().int
        async with self.r.client() as client:
            key = await self._create_key(data.url)
            await client.set(key, data.model_dump_json(), ex=self.expiry_seconds)

    async def get(
        self, command: command.SearchCacheGetCommand
    ) -> list[cache.SearchCache]:
        if not command.url:
            return []
        async with self.r.client() as client:
            key = await self._create_key(command.url)
            cached_data = await client.get(key)
            if not cached_data:
                return []
            try:
                return [cache.SearchCache(**json.loads(cached_data))]
            except Exception as e:
                return []

    async def _create_key(self, url: str) -> str:
        return self.HEADER + url
