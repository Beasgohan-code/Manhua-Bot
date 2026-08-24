# Manhua-Bot - Database entry point

from .base import BaseDB
from .users import UsersMixin
from .subs import SubsMixin
from .cache import CacheMixin
from .config import ConfigMixin
from .tasks import TasksMixin
from .admin import AdminMixin

class DB(BaseDB, UsersMixin, SubsMixin, CacheMixin, ConfigMixin, TasksMixin, AdminMixin):
    pass

db = DB()
