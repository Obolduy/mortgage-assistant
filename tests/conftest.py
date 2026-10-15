import pytest

from app.core import db


@pytest.fixture
def cleanup_jobs():
    ids = []
    yield ids
    with db.connection() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ANY(%s)", (ids,))
