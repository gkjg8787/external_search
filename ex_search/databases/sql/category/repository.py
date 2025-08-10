from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from domain.models.category import (
    repository as m_repository,
    category as m_category,
    command as m_command,
)


class CategoryRepository(m_repository.ICategoryRepository):
    session: AsyncSession

    def __init__(self, ses: AsyncSession):
        self.session = ses

    async def save_all(self, cate_entries: list[m_category.Category]):
        ses = self.session
        adds = []
        updates = []
        for cate in cate_entries:
            result = await ses.execute(
                select(m_category.Category)
                .where(m_category.Category.category_id == cate.category_id)
                .where(m_category.Category.entity_type == cate.entity_type)
            )
            db_cate = result.scalar()
            if db_cate:
                if db_cate.name != cate.name:
                    db_cate.name = cate.name
                    updates.append(cate)
                continue
            ses.add(cate)
            await ses.flush()
            adds.append(cate)
        await ses.commit()
        for cate in adds:
            await ses.refresh(cate)
        for cate in updates:
            await ses.refresh(cate)

    async def get(
        self, command: m_command.CategoryGetCommand
    ) -> list[m_category.Category]:
        ses = self.session
        stmt = select(m_category.Category)
        if command.category_id:
            stmt = stmt.where(m_category.Category.category_id == command.category_id)
        if command.name:
            stmt = stmt.where(m_category.Category.name == command.name)
        if command.entity_type:
            stmt = stmt.where(m_category.Category.entity_type == command.entity_type)
        result = await ses.execute(stmt)
        categorys = result.scalars()
        if not categorys:
            return []
        return categorys.all()
