from app.core import db
from app.core.config import settings
from app.rag import embedder
from app.repositories import chunks


def embed_pending(document_id: str | None = None) -> int:
    total = 0
    with db.connection() as conn:
        while batch := chunks.pending(conn, settings.embed_model, settings.embed_batch * 4, document_id):
            vectors = embedder.embed_documents([(c["section"], c["text"]) for c in batch])
            chunks.set_embeddings(conn, [(c["id"], v) for c, v in zip(batch, vectors)], settings.embed_model)
            total += len(batch)
    return total


if __name__ == "__main__":
    try:
        print(f"Пересчитано чанков: {embed_pending()}")
    finally:
        db.close_pool()
