-- On-Call Finder integration
-- Independent data model; does not modify Hub teams or roster tables.

CREATE TABLE IF NOT EXISTS oncall_uploads (
    id SERIAL PRIMARY KEY,
    file_key VARCHAR(191) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    stored_name VARCHAR(150) NOT NULL DEFAULT '',
    source_type VARCHAR(30) NOT NULL
        CHECK (source_type IN ('xlsx', 'msg', 'paste')),
    source_group VARCHAR(100) NOT NULL,
    period_start DATE,
    period_end DATE,
    rows_count INTEGER NOT NULL DEFAULT 0 CHECK (rows_count >= 0),
    file_sha256 CHAR(64) NOT NULL DEFAULT '',
    report JSONB,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT oncall_uploads_period_check
        CHECK (
            period_start IS NULL
            OR period_end IS NULL
            OR period_start <= period_end
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_oncall_uploads_current_file_key
    ON oncall_uploads(file_key)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS ix_oncall_uploads_history
    ON oncall_uploads(uploaded_at DESC);

CREATE INDEX IF NOT EXISTS ix_oncall_uploads_source_group
    ON oncall_uploads(source_group, uploaded_at DESC);

CREATE TABLE IF NOT EXISTS oncall_entries (
    id BIGSERIAL PRIMARY KEY,
    upload_id INTEGER NOT NULL
        REFERENCES oncall_uploads(id) ON DELETE CASCADE,
    source_group VARCHAR(100) NOT NULL,
    team VARCHAR(150) NOT NULL,
    duty_date DATE NOT NULL,
    shift_start TIME,
    shift_end TIME,
    person_name VARCHAR(150) NOT NULL DEFAULT '',
    role VARCHAR(50) NOT NULL DEFAULT '',
    phone VARCHAR(30) NOT NULL DEFAULT '',
    email VARCHAR(150) NOT NULL DEFAULT '',
    note VARCHAR(255) NOT NULL DEFAULT '',
    is_superseded BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS ix_oncall_entries_date
    ON oncall_entries(duty_date, is_superseded);

CREATE INDEX IF NOT EXISTS ix_oncall_entries_team_date
    ON oncall_entries(team, duty_date);

CREATE INDEX IF NOT EXISTS ix_oncall_entries_source_team_date
    ON oncall_entries(source_group, team, duty_date);

CREATE INDEX IF NOT EXISTS ix_oncall_entries_upload
    ON oncall_entries(upload_id);

-- On-Call permissions
-- Admin access is automatic in the existing permission engine.

INSERT INTO permissions
    (permission_key, name, description, category, is_active)
VALUES
    ('oncall.import', 'Import On-Call Data',
     'Upload and import Excel and Outlook On-Call files.', 'On-Call', TRUE),

    ('oncall.manual_import', 'Manually Import On-Call Data',
     'Import On-Call records using the manual paste form.', 'On-Call', TRUE),

    ('oncall.edit', 'Edit On-Call Data',
     'Modify imported On-Call records.', 'On-Call', TRUE),

    ('oncall.delete', 'Delete On-Call Imports',
     'Delete On-Call imports and their records.', 'On-Call', TRUE),

    ('oncall.history.view', 'View On-Call Import History',
     'View import history and previous versions.', 'On-Call', TRUE),

    ('oncall.manage', 'Manage On-Call Versions',
     'Activate previous versions and manage On-Call data.', 'On-Call', TRUE)

ON CONFLICT (permission_key) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    is_active = TRUE;
