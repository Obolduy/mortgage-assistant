from app.core.config import settings

_model = None


def model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embed_model, device="cpu")
    return _model


def doc_text(section: str, text: str) -> str:
    return settings.embed_doc_template.format(title=section or "none", text=text)


def embed_query(text: str) -> list[float]:
    return model().encode(settings.embed_query_prefix + text, normalize_embeddings=True, show_progress_bar=False).tolist()


def embed_documents(items: list[tuple[str, str]]) -> list[list[float]]:
    texts = [doc_text(section, text) for section, text in items]
    return model().encode(texts, batch_size=settings.embed_batch, normalize_embeddings=True,
                           show_progress_bar=False).tolist()
