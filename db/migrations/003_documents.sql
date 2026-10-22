CREATE TABLE documents (
    id           text PRIMARY KEY,
    filename     text NOT NULL,
    content      bytea NOT NULL,
    status       text NOT NULL,
    error        text,
    chunks_count integer NOT NULL DEFAULT 0,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id           bigserial PRIMARY KEY,
    document_id  text NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal      integer NOT NULL,
    text         text NOT NULL,
    kind         text NOT NULL,
    section      text NOT NULL,
    page         integer,
    sheet        text,
    row_no       integer,
    program_code text,
    embedding    vector(768),
    embed_model  text,
    tsv          tsvector GENERATED ALWAYS AS (to_tsvector('russian', text)) STORED,
    UNIQUE (document_id, ordinal)
);

CREATE INDEX chunks_tsv ON chunks USING gin (tsv);
CREATE INDEX chunks_program_code ON chunks (program_code);
