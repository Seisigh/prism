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

-- No migration framework at this scale (see the file header) -- an
-- idempotent ADD COLUMN IF NOT EXISTS is how this file self-migrates an
-- already-existing sessions table (e.g. a running local dev database)
-- the same way CREATE TABLE IF NOT EXISTS does for a brand new one.
-- The globally-active merchandising season (close-out item 4) at the
-- moment a session started, logged once and never updated, so a later
-- analysis can measure the season's effect on behavior. Purely a log
-- column -- never read by server/features/, sim/, or eval/.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS active_season TEXT;

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

-- A single-row-per-key config store. Currently holds exactly one key,
-- the active merchandising season (close-out item 4), changeable from
-- the admin console. Not a settings framework -- just enough table to
-- avoid a magic Redis key for something that should survive a cache
-- flush the same way sessions and events do.
CREATE TABLE IF NOT EXISTS app_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
