import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domain.schemas.search import InfoRequest, InfoResponse
from domain.schemas.search.info import CategoryInfo
from domain.models.category import repository as cate_repo, command as cate_cmd
from app.activitylog.update import UpdateActivityLog
from app.sofmap import category as sofmap_cate, constants as sofmap_const
from .enums import InfoName, SupportedSiteName, ActivityName


class SearchInfo:
    session: AsyncSession
    caller_type: str
    inforeq: InfoRequest
    category_repository: cate_repo.ICategoryRepository

    def __init__(
        self,
        ses: AsyncSession,
        caller_type: str,
        inforeq: InfoRequest,
        category_repo: cate_repo.ICategoryRepository,
    ):
        self.session = ses
        self.caller_type = caller_type
        self.inforeq = inforeq
        self.category_repository = category_repo

    async def execute(self) -> InfoResponse:
        inforeq: InfoRequest = self.inforeq
        upactlog = UpdateActivityLog(ses=self.session)
        init_subinfo = {"request": inforeq.model_dump()}
        target_table = f"{inforeq.sitename}.{inforeq.infoname}"
        tasklog = await upactlog.create(
            target_id=str(uuid.uuid4()),
            target_table=target_table,
            activity_type=ActivityName.SearchInfo.value,
            caller_type=self.caller_type,
            subinfo=init_subinfo,
        )

        if not tasklog:
            return InfoResponse(error_msg=f"task is not created")

        tasklog_id = tasklog.id
        match inforeq.sitename.lower():
            case SupportedSiteName.SOFMAP.value:
                response = await self._get_sofmap_info()
                if response.results and not response.error_msg:
                    await upactlog.completed(id=tasklog_id)
                elif response.results:
                    await upactlog.completed_with_error(
                        id=tasklog_id, error_msg=response.error_msg
                    )
                else:
                    await upactlog.failed(id=tasklog_id, error_msg=response.error_msg)
                return response
            case _:
                error_msg = f"not supported sitename : {inforeq.sitename}"
                await upactlog.failed(
                    id=tasklog_id,
                    error_msg=error_msg,
                )
                return InfoResponse(error_msg=error_msg)

    async def _get_sofmap_info(self) -> InfoResponse:
        inforeq: InfoRequest = self.inforeq
        match inforeq.infoname.lower():
            case InfoName.CATEGORY.value:
                return await self._get_sofmap_category()
            case _:
                return InfoResponse(
                    error_msg=f"not supported infoname : {inforeq.infoname}"
                )

    async def _get_sofmap_category(self):
        if self.inforeq.options.get("is_akiba"):
            entity_type = sofmap_const.A_SOFMAP_DB_ENTITY_TYPE
        else:
            entity_type = sofmap_const.SOFMAP_DB_ENTITY_TYPE
        getcmd = cate_cmd.CategoryGetCommand(entity_type=entity_type)
        results = await self.category_repository.get(command=getcmd)
        if not results:
            await sofmap_cate.create_category_data(ses=self.session)
            results = await self.category_repository.get(command=getcmd)
            if not results:
                return InfoResponse(error_msg="failed get category")
        categorylist = [CategoryInfo(gid=r.category_id, name=r.name) for r in results]
        return InfoResponse(results=categorylist)
