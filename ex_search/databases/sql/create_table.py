from domain.models.activitylog import activitylog
from domain.models.cache import cache
from domain.models.category import category
from domain.models.ai import ailog
from . import util as db_util


def create_table():
    db_util.create_db_and_tables()
