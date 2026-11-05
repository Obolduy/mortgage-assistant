import psycopg


def add(conn: psycopg.Connection, *, request_id: str | None, agent: str, model: str, tier: str, requests: int,
        input_tokens: int, output_tokens: int, cost_micros: int, duration_ms: int) -> None:
    conn.execute(
        """
        INSERT INTO llm_calls (request_id, agent, model, tier, requests, input_tokens, output_tokens, cost_micros,
                               duration_ms)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (request_id, agent, model, tier, requests, input_tokens, output_tokens, cost_micros, duration_ms),
    )
