-- 006_roster_draft_tracking.sql
-- Track the user and timestamp of the latest roster draft change.
-- Does NOT modify roster snapshots or version statuses.

BEGIN;

ALTER TABLE roster_versions
    ADD COLUMN IF NOT EXISTS updated_by BIGINT
        REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

-- Backfill existing versions.
-- For historical versions, the creator is the best available
-- representation of the last known modifier.
UPDATE roster_versions
SET
    updated_by = COALESCE(updated_by, created_by),
    updated_at = COALESCE(updated_at, created_at)
WHERE updated_by IS NULL
   OR updated_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_roster_versions_updated_by
    ON roster_versions(updated_by);

COMMIT;
