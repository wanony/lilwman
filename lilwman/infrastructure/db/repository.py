import re
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository
from .models import EntryModel, TagModel


class SQLAlchemyEntryRepository(EntryRepository):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def save(
        self,
        content: str,
        tags: list[str],
        author_id: str,
        author_name: str,
    ) -> Entry:
        now = datetime.now(timezone.utc)
        clean_tags = [t.strip() for t in tags if t.strip()]
        async with self._session_factory() as session:
            async with session.begin():
                entry_model = EntryModel(
                    content=content,
                    author_id=author_id,
                    author_name=author_name,
                    created_at=now,
                    updated_at=now,
                )
                session.add(entry_model)
                await session.flush()

                if clean_tags:
                    session.add_all(
                        TagModel(entry_id=entry_model.id, name=t) for t in clean_tags
                    )

                tags_str = " ".join(clean_tags)
                await session.execute(
                    text(
                        "INSERT INTO entries_fts(entry_id, content, tags) "
                        "VALUES (:eid, :c, :t)"
                    ),
                    {"eid": entry_model.id, "c": content, "t": tags_str},
                )

        return Entry(
            id=entry_model.id,
            content=content,
            tags=clean_tags,
            author_id=author_id,
            author_name=author_name,
            created_at=now,
            updated_at=now,
        )

    async def get_by_id(self, entry_id: int) -> Entry | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(EntryModel)
                .options(selectinload(EntryModel.tags))
                .where(EntryModel.id == entry_id)
            )
            model = result.scalar_one_or_none()
            if model is None:
                return None
            return self._to_entity(model)

    async def search(self, query: str, limit: int = 20) -> list[Entry]:
        cleaned = re.sub(r'[^\w\s]', ' ', query).strip()
        if not cleaned:
            return []
        tokens = cleaned.split()
        fts_query = ' OR '.join(tokens)
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        """
                        SELECT e.id FROM entries_fts f
                        JOIN entries e ON e.id = f.entry_id
                        WHERE entries_fts MATCH :q
                        ORDER BY rank
                        LIMIT :lim
                        """
                    ),
                    {"q": fts_query, "lim": limit},
                )
            ).fetchall()

            if not rows:
                return []

            ids = [r[0] for r in rows]
            result = await session.execute(
                select(EntryModel)
                .options(selectinload(EntryModel.tags))
                .where(EntryModel.id.in_(ids))
            )
            models_by_id = {m.id: m for m in result.scalars().all()}
            return [self._to_entity(models_by_id[i]) for i in ids if i in models_by_id]

    async def list_by_tag(self, tag: str) -> list[Entry]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(EntryModel)
                .options(selectinload(EntryModel.tags))
                .join(TagModel)
                .where(TagModel.name == tag)
                .order_by(EntryModel.created_at.desc())
            )
            return [self._to_entity(m) for m in result.scalars().unique().all()]

    async def delete(
        self, entry_id: int, author_id: str, is_admin: bool
    ) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(EntryModel).where(EntryModel.id == entry_id)
                )
                model = result.scalar_one_or_none()
                if model is None:
                    return False
                if not is_admin and model.author_id != author_id:
                    return False
                await session.delete(model)
                await session.execute(
                    text("DELETE FROM entries_fts WHERE entry_id = :eid"),
                    {"eid": entry_id},
                )
                return True

    def _to_entity(self, model: EntryModel) -> Entry:
        return Entry(
            id=model.id,
            content=model.content,
            tags=[t.name for t in model.tags],
            author_id=model.author_id,
            author_name=model.author_name,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
