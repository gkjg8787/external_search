from celery import Celery

app = Celery("ex_search", broker="redis://redis:6379/0", backend="redis://redis:6379/0")

# タスクのルーティング設定
app.conf.update(
    task_routes={
        "tasks.sofmap_dl_task": {"queue": "sofmap_work_queue"},
        #'tasks.normal_task': {'queue': 'default'},
    }
)
