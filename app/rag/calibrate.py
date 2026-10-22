from app.core import db
from app.core.config import settings
from app.rag import embedder
from app.repositories import chunks

RELEVANT = [
    ("есть ли комиссия за досрочное погашение", "без комиссий и штрафов"),
    ("какая минимальная сумма частичного досрочного погашения", "Минимальная сумма частичного"),
    ("что выгоднее: сократить срок или уменьшить платеж", "экономия на процентах"),
    ("когда пересчитают график после досрочки", "Новый график платежей формируется"),
    ("на какое число можно перенести платеж", "только с 1 по 28"),
    ("как считаются проценты при смене даты платежа", "по фактическому числу дней"),
    ("сколько рассматривают заявление на смену даты", "в течение 2 рабочих дней"),
    ("какая неустойка за просрочку платежа", "неустойку 0,06%"),
    ("какая ставка по семейной ипотеке", "Семейная ипотека"),
    ("сколько стоит дубликат договора", "Дубликат кредитного договора"),
    ("справка о процентах для налогового вычета", "налогового вычета"),
]

OFF_TOPIC = [
    "как приготовить борщ",
    "погода в Москве завтра",
    "кто выиграл чемпионат мира по футболу",
    "посоветуй хороший сериал",
    "как поменять масло в машине",
]


def scores(conn, query: str) -> list[dict]:
    return chunks.search_vector(conn, embedder.embed_query(query), 100, -1.0)


def main() -> None:
    print(f"модель: {settings.embed_model}\n")
    with db.connection() as conn:
        relevant = []
        for query, expected in RELEVANT:
            hits = scores(conn, query)
            rank = next(i for i, h in enumerate(hits, 1) if expected in h["text"])
            relevant.append(hits[rank - 1]["score"])
            print(f"{hits[rank - 1]['score']:.3f}  место {rank}  {query}")
        print()
        noise = []
        for query in OFF_TOPIC:
            top = scores(conn, query)[0]["score"]
            noise.append(top)
            print(f"{top:.3f}  лучший  {query}")
    low, high = min(relevant), max(noise)
    print(f"\nхудший нужный: {low:.3f}, лучший мусор: {high:.3f}")
    if low > high:
        print(f"порог посередине: {(low + high) / 2:.2f}")
    else:
        print("порог не разделяет: часть нужных ниже мусора")


if __name__ == "__main__":
    try:
        main()
    finally:
        db.close_pool()
