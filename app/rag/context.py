import re

SOURCE_ID = re.compile(r"^\[(\d+) \|", re.MULTILINE)


def label(hit: dict) -> str:
    where = [hit["filename"]]
    if hit["sheet"]:
        where.append(f"{hit['sheet']}, строка {hit['row_no']}")
    else:
        where += [f"стр. {hit['page']}"] if hit["page"] else []
        where += [hit["section"]] if hit["section"] else []
    return " | ".join(where)


def build_context(hits: list[dict], max_chars: int) -> str:
    parts, seen, size = [], set(), 0
    for hit in hits:
        if hit["text"] in seen:
            continue
        block = f"[{hit['id']} | {label(hit)}]\n{hit['text']}"
        if parts and size + len(block) > max_chars:
            break
        seen.add(hit["text"])
        parts.append(block)
        size += len(block)
    return "\n\n".join(parts) or "Ничего не найдено."


def source_ids(context: str) -> set[int]:
    return {int(i) for i in SOURCE_ID.findall(context)}
