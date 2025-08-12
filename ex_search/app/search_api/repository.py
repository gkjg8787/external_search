import json
from datetime import datetime, timezone

import redis.asyncio as aredis


class URLDomainCacheRepository:
    HEADER = "domain:"
    r: aredis.Redis
    expiry_seconds: int

    def __init__(self, r: aredis.Redis, expiry_seconds: int | None = None):
        self.r = r
        if expiry_seconds:
            self.expiry_seconds = expiry_seconds
        else:
            self.expiry_seconds = 3600

    async def save(self, domain: str):
        now = datetime.now(timezone.utc)
        async with self.r.client() as client:
            key = await self._create_key(domain)
            await client.set(key, now.isoformat(), ex=self.expiry_seconds)

    async def get(self, domain: str) -> datetime | None:
        if not domain:
            return None
        async with self.r.client() as client:
            key = await self._create_key(domain)
            cached_data = await client.get(key)
            if not cached_data:
                return None
            if isinstance(cached_data, bytes):
                cached_data = cached_data.decode("utf-8")
            return datetime.fromisoformat(cached_data)

    async def _create_key(self, key: str) -> str:
        return self.HEADER + key
