from datetime import datetime, timezone

import redis.asyncio as aredis


class URLDomainCacheRepository:
    r: aredis.Redis
    expiry_seconds: int

    def __init__(self, r: aredis.Redis, expiry_seconds: int | None = None):
        self.r = r
        if expiry_seconds:
            self.expiry_seconds = expiry_seconds
        else:
            self.expiry_seconds = 3600

    async def save(self, domain: str, status: str, expiry_seconds: int | None = None):
        now = datetime.now(timezone.utc)
        async with self.r.client() as client:
            key = await self._create_key(domain)
            data = {"status": status, "updated_at": now.isoformat()}
            await client.hset(key, mapping=data)
            if expiry_seconds:
                await client.expire(key, expiry_seconds)
            else:
                await client.expire(key, self.expiry_seconds)

    async def get(self, domain: str) -> datetime | None:
        if not domain:
            return None
        async with self.r.client() as client:
            key = await self._create_key(domain)
            cached_data = await client.hgetall(key)
            if not cached_data:
                return None

            def _decode_data(v):
                if isinstance(v, bytes):
                    return v.decode("utf-8")
                return v

            decoded_data = {
                _decode_data(k): _decode_data(v) for k, v in cached_data.items()
            }
            if decoded_data.get("updated_at"):
                decoded_data["updated_at"] = datetime.fromisoformat(
                    decoded_data["updated_at"]
                )
            return decoded_data

    async def delete_all(self):
        async with self.r.client() as client:
            key = await self._create_key("*")
            domain_keys = await client.keys(key)
            if domain_keys:
                await client.delete(*domain_keys)

    async def _create_key(self, key: str) -> str:
        return f"domain:{key}:data"
