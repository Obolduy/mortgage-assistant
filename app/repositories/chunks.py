import psycopg
from psycopg.rows import dict_row

RRF_K = 60

BASE = """
    base AS (
        SELECT c.id, c.text, c.embedding, c.tsv, c.section, c.page, c.sheet, c.row_no, c.program_code,
               d.filename
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE d.status = 'indexed' AND (%(filename)s::text IS NULL OR d.filename = %(filename)s)
    )
"""

FIELDS = "b.id, b.text, b.filename, b.section, b.page, b.sheet, b.row_no, b.program_code"


def vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def _fetch(conn: psycopg.Connection, sql: str, params: dict) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def pending(conn: psycopg.Connection, model: str, limit: int, document_id: str | None = None) -> list[dict]:
    return _fetch(
        conn,
        """
        SELECT id, section, text FROM chunks
        WHERE (embedding IS NULL OR embed_model IS DISTINCT FROM %(model)s)
          AND (%(doc)s::text IS NULL OR document_id = %(doc)s)
        ORDER BY id
        LIMIT %(limit)s
        """,
        {"model": model, "doc": document_id, "limit": limit},
    )


def set_embeddings(conn: psycopg.Connection, items: list[tuple[int, list[float]]], model: str) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            "UPDATE chunks SET embedding = %s::vector, embed_model = %s WHERE id = %s",
            [(vector_literal(vec), model, chunk_id) for chunk_id, vec in items],
        )


def search_vector(conn: psycopg.Connection, vec: list[float], top_k: int, threshold: float,
                  filename: str | None = None) -> list[dict]:
    return _fetch(
        conn,
        f"""
        WITH {BASE}
        SELECT {FIELDS}, 1 - (b.embedding <=> %(vec)s::vector) AS score
        FROM base b
        WHERE b.embedding IS NOT NULL AND 1 - (b.embedding <=> %(vec)s::vector) >= %(threshold)s
        ORDER BY b.embedding <=> %(vec)s::vector
        LIMIT %(top_k)s
        """,
        {"vec": vector_literal(vec), "threshold": threshold, "top_k": top_k, "filename": filename},
    )


def search_fts(conn: psycopg.Connection, query: str, top_k: int, filename: str | None = None) -> list[dict]:
    return _fetch(
        conn,
        f"""
        WITH {BASE}
        SELECT {FIELDS}, ts_rank(b.tsv, q) AS score
        FROM base b, plainto_tsquery('russian', %(query)s) q
        WHERE b.tsv @@ q
        ORDER BY score DESC, b.id
        LIMIT %(top_k)s
        """,
        {"query": query, "top_k": top_k, "filename": filename},
    )


def search_hybrid(conn: psycopg.Connection, query: str, vec: list[float], top_k: int, threshold: float,
                  filename: str | None = None) -> list[dict]:
    return _fetch(
        conn,
        f"""
        WITH {BASE},
        vec AS (
            SELECT b.id, row_number() OVER (ORDER BY b.embedding <=> %(vec)s::vector) AS rank
            FROM base b
            WHERE b.embedding IS NOT NULL AND 1 - (b.embedding <=> %(vec)s::vector) >= %(threshold)s
            ORDER BY b.embedding <=> %(vec)s::vector
            LIMIT %(pool)s
        ),
        fts AS (
            SELECT b.id, row_number() OVER (ORDER BY ts_rank(b.tsv, q) DESC, b.id) AS rank
            FROM base b, plainto_tsquery('russian', %(query)s) q
            WHERE b.tsv @@ q
            ORDER BY rank
            LIMIT %(pool)s
        )
        SELECT {FIELDS},
               coalesce(1.0 / (%(k)s + vec.rank), 0) + coalesce(1.0 / (%(k)s + fts.rank), 0) AS score
        FROM vec FULL JOIN fts USING (id)
        JOIN base b ON b.id = coalesce(vec.id, fts.id)
        ORDER BY score DESC, b.id
        LIMIT %(top_k)s
        """,
        {"vec": vector_literal(vec), "query": query, "threshold": threshold, "pool": top_k * 4,
         "k": RRF_K, "top_k": top_k, "filename": filename},
    )


def by_program_codes(conn: psycopg.Connection, codes: list[str], filename: str | None = None) -> list[dict]:
    if not codes:
        return []
    return _fetch(
        conn,
        f"""
        WITH {BASE}
        SELECT {FIELDS}, 1.0 AS score
        FROM base b
        WHERE b.program_code = ANY(%(codes)s)
        ORDER BY b.sheet NULLS LAST, b.id
        """,
        {"codes": codes, "filename": filename},
    )


def existing(conn: psycopg.Connection, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    return {row[0] for row in conn.execute("SELECT id FROM chunks WHERE id = ANY(%s)", (ids,)).fetchall()}
