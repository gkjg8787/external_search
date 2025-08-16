from common.read_config import get_redis_options
import redis.asyncio as a_redis


def get_async_redis(
    host: str | None = None, port: int | None = None, db: int | None = None
):
    redisopts = get_redis_options()
    params = {}
    if host is None:
        params["host"] = redisopts.host
    else:
        params["host"] = host
    if port is None:
        params["port"] = redisopts.port
    else:
        params["post"] = port
    if db is None:
        params["db"] = redisopts.db
    else:
        params["db"] = db
    return a_redis.Redis(**params)
