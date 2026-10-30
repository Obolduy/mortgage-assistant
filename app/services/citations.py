from app.core import db
from app.rag.context import source_ids
from app.repositories import chunks


def seen_sources(outputs: list[str]) -> set[int]:
    return source_ids("\n".join(outputs))


def citation_error(sources: list[int], seen: set[int]) -> str | None:
    if seen and not sources:
        return "ответ по документам без источников: перечисли в sources номера фрагментов, на которые опираешься"
    unseen = sorted(set(sources) - seen)
    if unseen:
        return f"источников {unseen} не было среди найденных фрагментов, ссылайся только на них"
    with db.connection() as conn:
        missing = sorted(set(sources) - chunks.existing(conn, sources))
    if missing:
        return f"фрагментов {missing} нет в базе"
    return None
