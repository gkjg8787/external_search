import asyncio

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from sofmap.parser import CategoryParser
from sofmap.model import CategoryResult
from domain.models.category import (
    repository as cate_repo,
    category as m_category,
    command as cate_cmd,
)
from databases.sql.category.repository import CategoryRepository

from .constants import (
    SOFMAP_TOP_URL,
    A_SOFMAP_TOP_URL,
    SOFMAP_DB_ENTITY_TYPE,
    A_SOFMAP_DB_ENTITY_TYPE,
)


async def dl_sofmap_top(
    url: str, max_retries: int = 2, delay_seconds: int = 1, timeout: int = 4
):
    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries + 1):
            try:
                res = await client.get(url, timeout=timeout)
                res.raise_for_status()
                return res.text
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt < max_retries:
                    await asyncio.sleep(delay_seconds)
                else:
                    raise e
            except Exception as e:
                raise e


def convert_categoryresult_to_categorydomain(
    result: CategoryResult, entity_type: str
) -> list[m_category.Category]:
    domain_list: list[m_category.Category] = []
    for gid, name in result.gid_to_name.items():
        domain_list.append(
            m_category.Category(category_id=gid, name=name, entity_type=entity_type)
        )
    return domain_list


async def create_category_data(ses: AsyncSession):
    async def dl_and_create_category(
        url, repository: cate_repo.ICategoryRepository, entity_type: str
    ):
        try:
            top_text = await dl_sofmap_top(url=url)
            cp = CategoryParser(html_str=top_text)
            cp.execute()
            category_list = convert_categoryresult_to_categorydomain(
                result=cp.get_results(), entity_type=entity_type
            )
            await repository.save_all(cate_entries=category_list)
        except Exception:
            return

    repository = CategoryRepository(ses=ses)
    await dl_and_create_category(
        url=SOFMAP_TOP_URL, repository=repository, entity_type=SOFMAP_DB_ENTITY_TYPE
    )
    await dl_and_create_category(
        url=A_SOFMAP_TOP_URL, repository=repository, entity_type=A_SOFMAP_DB_ENTITY_TYPE
    )


async def get_category_id(
    ses: AsyncSession,
    is_akiba: bool,
    category_name: str,
) -> str:
    if not category_name:
        return ""
    repository = CategoryRepository(ses=ses)
    if is_akiba:
        entity_type = A_SOFMAP_DB_ENTITY_TYPE
    else:
        entity_type = SOFMAP_DB_ENTITY_TYPE
    getcmd = cate_cmd.CategoryGetCommand(name=category_name, entity_type=entity_type)
    results = await repository.get(command=getcmd)
    if not results:
        await create_category_data(ses=ses)

    results = await repository.get(command=getcmd)
    if not results:
        return ""
    return results[0].category_id
