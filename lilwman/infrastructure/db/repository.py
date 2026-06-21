import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete, func, select, text
from sqlalchemy.orm import selectinload

from lilwman.domain.entities import Entry
from lilwman.domain.ports import EntryRepository
from .models import EntryModel, TagModel

_FTS5_RESERVED = frozenset({"and", "or", "not"})


def _sanitize_fts_query(query: str) -> str:
    # Strip FTS5 special chars
    cleaned = re.sub(r'[^\w\s]', ' ', query)
    # Filter reserved words and empty tokens
    tokens = [t for t in cleaned.split() if t.lower() not in _FTS5_RESERVED]
    return ' '.join(tokens)


class SQLAlchemyEntryRepository(EntryRepository):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def save(
        self,
        content: str,
        tags: list[str],
        author_id: str,
        author_name: str,
        guild_id: str = "",
    ) -> Entry:
        now = datetime.now(timezone.utc)
        clean_tags = [t.strip().lower() for t in tags if t.strip()]
        async with self._session_factory() as session:
            async with session.begin():
                entry_model = EntryModel(
                    content=content,
                    author_id=author_id,
                    author_name=author_name,
                    guild_id=guild_id,
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
            guild_id=guild_id,
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
        fts_query = _sanitize_fts_query(query)
        if not fts_query:
            return []
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
                .where(TagModel.name == tag.lower())
                .order_by(EntryModel.created_at.desc())
                .limit(10)
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

    async def list_by_author(self, author_id: str, guild_id: str = "") -> list[Entry]:
        async with self._session_factory() as session:
            q = (
                select(EntryModel)
                .options(selectinload(EntryModel.tags))
                .where(EntryModel.author_id == author_id)
                .order_by(EntryModel.created_at.desc())
            )
            if guild_id:
                q = q.where(EntryModel.guild_id == guild_id)
            result = await session.execute(q)
            return [self._to_entity(m) for m in result.scalars().unique().all()]

    async def list_all(
        self, guild_id: str = "", offset: int = 0, limit: int = 20
    ) -> tuple[list[Entry], int]:
        async with self._session_factory() as session:
            count_q = select(func.count(EntryModel.id))
            q = (
                select(EntryModel)
                .options(selectinload(EntryModel.tags))
                .order_by(EntryModel.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            if guild_id:
                count_q = count_q.where(EntryModel.guild_id == guild_id)
                q = q.where(EntryModel.guild_id == guild_id)
            total = (await session.execute(count_q)).scalar() or 0
            result = await session.execute(q)
            return [self._to_entity(m) for m in result.scalars().unique().all()], total

    async def update(self, entry_id: int, content: str, tags: list[str]) -> Entry | None:
        now = datetime.now(timezone.utc)
        clean_tags = [t.strip().lower() for t in tags if t.strip()]
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(EntryModel)
                    .options(selectinload(EntryModel.tags))
                    .where(EntryModel.id == entry_id)
                )
                model = result.scalar_one_or_none()
                if model is None:
                    return None
                model.content = content
                model.updated_at = now
                for tag in list(model.tags):
                    await session.delete(tag)
                await session.flush()
                session.add_all(
                    TagModel(entry_id=model.id, name=t) for t in clean_tags
                )
                await session.execute(
                    text("DELETE FROM entries_fts WHERE entry_id = :eid"),
                    {"eid": entry_id},
                )
                tags_str = " ".join(clean_tags)
                await session.execute(
                    text(
                        "INSERT INTO entries_fts(entry_id, content, tags) "
                        "VALUES (:eid, :c, :t)"
                    ),
                    {"eid": entry_id, "c": content, "t": tags_str},
                )
        return Entry(
            id=model.id,
            content=content,
            tags=clean_tags,
            author_id=model.author_id,
            author_name=model.author_name,
            guild_id=model.guild_id,
            created_at=model.created_at,
            updated_at=now,
        )

    async def get_stats(self, guild_id: str) -> dict:
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        async with self._session_factory() as session:
            def _gf(q):
                return q.where(EntryModel.guild_id == guild_id) if guild_id else q

            total = (await session.execute(_gf(select(func.count(EntryModel.id))))).scalar() or 0

            week_q = select(func.count(EntryModel.id)).where(EntryModel.created_at >= week_ago)
            entries_this_week = (await session.execute(_gf(week_q))).scalar() or 0

            month_q = select(func.count(EntryModel.id)).where(EntryModel.created_at >= month_ago)
            entries_this_month = (await session.execute(_gf(month_q))).scalar() or 0

            tag_count_q = select(func.count(TagModel.name.distinct())).join(
                EntryModel, TagModel.entry_id == EntryModel.id
            )
            if guild_id:
                tag_count_q = tag_count_q.where(EntryModel.guild_id == guild_id)
            unique_tags = (await session.execute(tag_count_q)).scalar() or 0

            top_tags_q = (
                select(TagModel.name, func.count(TagModel.id).label("cnt"))
                .join(EntryModel, TagModel.entry_id == EntryModel.id)
                .group_by(TagModel.name)
                .order_by(func.count(TagModel.id).desc())
                .limit(10)
            )
            if guild_id:
                top_tags_q = top_tags_q.where(EntryModel.guild_id == guild_id)
            top_tags = [(r[0], r[1]) for r in (await session.execute(top_tags_q)).fetchall()]

            top_authors_q = (
                select(EntryModel.author_name, func.count(EntryModel.id).label("cnt"))
                .group_by(EntryModel.author_name)
                .order_by(func.count(EntryModel.id).desc())
                .limit(10)
            )
            top_authors = [(r[0], r[1]) for r in (await session.execute(_gf(top_authors_q))).fetchall()]

        return {
            "total_entries": total,
            "entries_this_week": entries_this_week,
            "entries_this_month": entries_this_month,
            "unique_tags": unique_tags,
            "top_tags": top_tags,
            "top_authors": top_authors,
        }

    async def purge_by_author(self, author_id: str, guild_id: str = "") -> int:
        async with self._session_factory() as session:
            async with session.begin():
                q = select(EntryModel.id).where(EntryModel.author_id == author_id)
                if guild_id:
                    q = q.where(EntryModel.guild_id == guild_id)
                ids = [r[0] for r in (await session.execute(q)).fetchall()]
                if not ids:
                    return 0
                placeholders = ",".join(str(i) for i in ids)
                await session.execute(text(f"DELETE FROM entries_fts WHERE entry_id IN ({placeholders})"))
                await session.execute(sa_delete(EntryModel).where(EntryModel.id.in_(ids)))
                return len(ids)

    async def purge_by_tag(self, tag: str, guild_id: str = "") -> int:
        clean_tag = tag.strip().lower()
        async with self._session_factory() as session:
            async with session.begin():
                q = (
                    select(EntryModel.id)
                    .join(TagModel, EntryModel.id == TagModel.entry_id)
                    .where(TagModel.name == clean_tag)
                )
                if guild_id:
                    q = q.where(EntryModel.guild_id == guild_id)
                ids = [r[0] for r in (await session.execute(q)).fetchall()]
                if not ids:
                    return 0
                placeholders = ",".join(str(i) for i in ids)
                await session.execute(text(f"DELETE FROM entries_fts WHERE entry_id IN ({placeholders})"))
                await session.execute(sa_delete(EntryModel).where(EntryModel.id.in_(ids)))
                return len(ids)

    def _to_entity(self, model: EntryModel) -> Entry:
        return Entry(
            id=model.id,
            content=model.content,
            tags=[t.name for t in model.tags],
            author_id=model.author_id,
            author_name=model.author_name,
            guild_id=model.guild_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
