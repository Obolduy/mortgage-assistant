import sys

from app.core import db
from app.core.config import settings
from app.parsers.chunker import PROGRAM_CODE
from app.rag import embedder
from app.repositories import chunks

MODES = ("hybrid", "vector", "fts")


def search(query: str, mode: str = "hybrid", top_k: int | None = None, filename: str | None = None,
           threshold: float | None = None) -> list[dict]:
    top_k = top_k or settings.search_top_k
    threshold = settings.search_threshold if threshold is None else threshold
    with db.connection() as conn:
        if mode == "fts":
            return chunks.search_fts(conn, query, top_k, filename)
        vec = embedder.embed_query(query)
        if mode == "vector":
            return chunks.search_vector(conn, vec, top_k, threshold, filename)
        exact = chunks.by_program_codes(conn, PROGRAM_CODE.findall(query.upper()), filename)
        found = chunks.search_hybrid(conn, query, vec, top_k, threshold, filename)
    seen = {c["id"] for c in exact}
    return (exact + [c for c in found if c["id"] not in seen])[:top_k]


if __name__ == "__main__":
    mode = sys.argv[2] if len(sys.argv) > 2 else "hybrid"
    try:
        for c in search(sys.argv[1], mode):
            print(f"{c['score']:.3f}  {c['filename']} · {c['section'] or '—'}\n    {c['text'][:160]}\n")
    finally:
        db.close_pool()
