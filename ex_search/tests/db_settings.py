import settings

DATABASES = {
    "sync": {
        "drivername": "sqlite",
        "database": f"{settings.BASE_DIR}/db/test_database.db",
    },
    "a_sync": {
        "drivername": "sqlite+aiosqlite",
        "database": f"{settings.BASE_DIR}/db/test_database.db",
    },
}
