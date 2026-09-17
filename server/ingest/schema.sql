-- PRISM ingest schema. Applied by server/ingest/db.py on startup (no
-- migration framework at this scale — "no ORM heroics" per §2).
--
-- Non-negotiable #5: session_id is a random UUID, no accounts, no PII.
-- IP address is never a column here and must never be added.

CREATE TABLE IF NOT EXISTS sessions (
    session_id      UUID PRIMARY KEY,
    code            TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_event_at   TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    demo_opened     BOOLEAN NOT NULL DEFAULT false,
    browser         TEXT,
    engine_version  TEXT,
    device_pixel_ratio REAL,
    viewport_width  INT,
    viewport_height INT,
    pointer_type    TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_code ON sessions (code);

CREATE TABLE IF NOT EXISTS events (
    event_id    UUID PRIMARY KEY,
    session_id  UUID NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    seq         INT NOT NULL,
    ts_mono     DOUBLE PRECISION NOT NULL,
    ts_wall     TIMESTAMPTZ NOT NULL,
    demo        BOOLEAN NOT NULL,
    surface     TEXT NOT NULL,
    mode        TEXT,
    type        TEXT NOT NULL,
    payload     JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_events_session_ts ON events (session_id, ts_mono);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (type);
