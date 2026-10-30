CREATE TABLE llm_calls (
    id            bigserial PRIMARY KEY,
    request_id    text,
    agent         text NOT NULL,
    model         text NOT NULL,
    requests      integer NOT NULL,
    input_tokens  integer NOT NULL,
    output_tokens integer NOT NULL,
    cost_micros   bigint NOT NULL,
    duration_ms   integer NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX llm_calls_request ON llm_calls (request_id);
