from domain.models.activitylog import command as act_cmd, enums as act_enums
from .update import UpdateActivityLog


async def get_activitylog_latest(
    upactivitylog: UpdateActivityLog,
    activity_types: list[str],
    current_states: list[str] | None = [
        act_enums.UpdateStatus.COMPLETED.name,
        act_enums.UpdateStatus.COMPLETED_WITH_ERRORS.name,
    ],
    target_table: str = "",
):
    db_actlogs = await upactivitylog.get_all(
        command=act_cmd.ActivityLogGetCommand(
            activity_types=activity_types,
            current_states=current_states,
            target_table=target_table,
        )
    )
    if not db_actlogs:
        return None
    lastest_actlog = max(db_actlogs, key=lambda log: log.updated_at)
    return lastest_actlog
