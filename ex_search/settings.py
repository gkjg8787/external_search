from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASES = {
    "sync": {
        "drivername": "sqlite",
        "database": f"{BASE_DIR}/db/database.db",
    },
    "a_sync": {
        "drivername": "sqlite+aiosqlite",
        "database": f"{BASE_DIR}/db/database.db",
    },
}
REDIS_OPTIONS = {
    "host": "redis",
    "port": 6379,
    "db": 0,
}
SELENIUM_OPTIONS = {
    "REMOTE_URL": "http://selenium:4444/wd/hub",
}
SOFMAP_OPTIONS = {
    "selenium": {
        "PAGE_LOAD_TIMEOUT": 30,
        "TAG_WAIT_TIMEOUT": 15,
    }
}
LOG_OPTIONS = {"directory_path": f"{BASE_DIR}/log/"}
CACHE_OPTIONS = {
    "expires": 300,
    "backend": "redis",
}
DOWNLOAD_WAITTIME_OPTIONS = {
    "timeout_for_each_url": 60,
    "timeout_util_downloadable": 300,
    "min_wait_time_of_dl": 1,
}
SEARCH_OPTIONS = {
    "safe_search": True,
}
