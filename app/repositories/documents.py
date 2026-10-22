import psycopg
from psycopg.rows import dict_row

from app.parsers.chunker import Chunk

COLUMNS = "id, filename, status, error, chunks_count, created_at, updated_at"


def create(conn: psycopg.Connection, doc_id: str, filename: str, content: bytes) -> bool:
    row = conn.execute(
        """
        INSERT INTO documents (id, filename, content, status) VALUES (%s, %s, %s, 'uploaded')
        ON CONFLICT (id) DO NOTHING
        RETURNING id
        """,
        (doc_id, filename, content),
    ).fetchone()
    return row is not None


def get(conn: psycopg.Connection, doc_id: str) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT {COLUMNS} FROM documents WHERE id = %s", (doc_id,))
        return cur.fetchone()


def content(conn: psycopg.Connection, doc_id: str) -> tuple[str, bytes]:
    return conn.execute("SELECT filename, content FROM documents WHERE id = %s", (doc_id,)).fetchone()


def set_status(conn: psycopg.Connection, doc_id: str, status: str, error: str | None = None) -> None:
    conn.execute(
        "UPDATE documents SET status = %s, error = %s, updated_at = now() WHERE id = %s",
        (status, error, doc_id),
    )


def replace_chunks(conn: psycopg.Connection, doc_id: str, chunks: list[Chunk]) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
        cur.executemany(
            """
            INSERT INTO chunks (document_id, ordinal, text, kind, section, page, sheet, row_no, program_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [(doc_id, c.ordinal, c.text, c.kind, c.section, c.page, c.sheet, c.row, c.program_code)
             for c in chunks],
        )
        cur.execute("UPDATE documents SET chunks_count = %s WHERE id = %s", (len(chunks), doc_id))
