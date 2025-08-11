import asyncio

from celerybase import app
from app.sofmap.tasks import download_task


@app.task
def sofmap_dl_task(url):
    return asyncio.run(download_task(url))
