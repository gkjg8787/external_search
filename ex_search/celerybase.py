from celery import Celery

from common.read_config import get_redis_options

redisopts = get_redis_options()
redis_url = f"redis://{redisopts.host}:{redisopts.port}/{redisopts.db}"
app = Celery("ex_search", broker=redis_url, backend=redis_url)

# タスクのルーティング設定
app.conf.update(
    task_routes={
        "tasks.sofmap_dl_task": {"queue": "sofmap_work_queue"},
    }
)
