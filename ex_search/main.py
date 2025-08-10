from contextlib import asynccontextmanager

from fastapi import FastAPI

from routers import (
    api,
)
from databases.sql.create_table import create_table


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_table()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(api.router)
