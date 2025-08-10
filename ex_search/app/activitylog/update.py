import datetime
import copy

from sqlalchemy.ext.asyncio import AsyncSession

from domain.models.activitylog import (
    command as act_cmd,
    activitylog as m_actlog,
    enums as actlog_enums,
)
from databases.sql.activitylog import repository as a_repo


class UpdateActivityLog:
    session: AsyncSession
    repository: a_repo.ActivityLogRepository

    def __init__(self, ses: AsyncSession):
        self.session = ses
        self.repository = a_repo.ActivityLogRepository(ses=ses)

    async def create(
        self,
        target_id: int,
        target_table: str = "None",
        activity_type: str = "",
        status: str = actlog_enums.UpdateStatus.PENDING.name,
        caller_type: str = "",
        subinfo: dict = {},
        error_msg: str = "",
    ) -> m_actlog.ActivityLog | None:
        activitylog = m_actlog.ActivityLog(
            target_id=target_id,
            target_table=target_table,
            activity_type=activity_type,
            current_state=status,
            caller_type=caller_type,
            meta=convert_datetime_to_str_in_dict(subinfo),
            error_msg=error_msg,
        )
        await self.repository.save_all([activitylog])
        await self.session.refresh(activitylog)
        return activitylog

    async def get(self, command: act_cmd.ActivityLogGetCommand):
        ret = await self.repository.get(command=command)
        if ret:
            return ret[0]
        return None

    async def get_all(self, command: act_cmd.ActivityLogGetCommand):
        return await self.repository.get(command=command)

    async def update(
        self,
        id: int,
        next_status: str | None = None,
        new_subinfo: dict | None = None,
        add_subinfo: dict | None = None,
        error_msg: str | None = None,
        add_error_msg: str | None = None,
    ) -> m_actlog.ActivityLog:
        db_actlog = await self.get(command=act_cmd.ActivityLogGetCommand(id=id))
        if not db_actlog:
            ValueError(f"{id} is not found in ActivityLog")
        if next_status:
            db_actlog.current_state = next_status
        if new_subinfo is not None and isinstance(new_subinfo, dict):
            db_actlog.meta = convert_datetime_to_str_in_dict(targets=new_subinfo)
        if add_subinfo and isinstance(add_subinfo, dict):
            db_actlog.meta = copy.deepcopy(
                db_actlog.meta
            ) | convert_datetime_to_str_in_dict(targets=add_subinfo)
        if error_msg is not None:
            db_actlog.error_msg = error_msg
        if add_error_msg:
            db_actlog.error_msg += add_error_msg
        await self.repository.save_all([db_actlog])
        await self.session.refresh(db_actlog)
        return db_actlog

    async def in_progress(self, id: int):
        return await self.update(
            id=id, next_status=actlog_enums.UpdateStatus.IN_PROGRESS.name
        )

    async def failed(
        self,
        id: int,
        error_msg: str | None = None,
        add_subinfo: dict | None = None,
    ):

        return await self.update(
            id=id,
            next_status=actlog_enums.UpdateStatus.FAILED.name,
            add_subinfo=add_subinfo,
            error_msg=error_msg,
        )

    async def canceled(
        self,
        id: int,
        error_msg: str | None = None,
        add_subinfo: dict | None = None,
    ):
        return await self.update(
            id=id,
            next_status=actlog_enums.UpdateStatus.CANCELED.name,
            add_subinfo=add_subinfo,
            error_msg=error_msg,
        )

    async def completed(
        self,
        id: int,
        add_subinfo: dict | None = None,
    ):
        return await self.update(
            id=id,
            next_status=actlog_enums.UpdateStatus.COMPLETED.name,
            add_subinfo=add_subinfo,
        )

    async def completed_with_error(
        self,
        id: int,
        error_msg: str | None = None,
        add_subinfo: dict | None = None,
    ):
        return await self.update(
            id=id,
            next_status=actlog_enums.UpdateStatus.COMPLETED_WITH_ERRORS.name,
            add_subinfo=add_subinfo,
            error_msg=error_msg,
        )


def convert_datetime_to_str(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return str(value)  # value.strftime("%Y-%m-%d %H:%M:%S.%f")
    elif isinstance(value, dict):
        return convert_datetime_to_str_in_dict(value)
    elif isinstance(value, list):
        converted_list = []
        for v in value:
            converted_list.append(convert_datetime_to_str(v))
        return converted_list
    else:
        return value


def convert_datetime_to_str_in_dict(targets: dict) -> dict:
    converted = {}
    for key, value in targets.items():
        converted[key] = convert_datetime_to_str(value)
    return converted
