-- 005_roster_draft_publish.sql
-- Safe Roster Draft/Publish foundation.
-- Does NOT modify or delete the existing roster_* data.

BEGIN;

CREATE TABLE IF NOT EXISTS roster_versions (
    id BIGSERIAL PRIMARY KEY,
    version_number INTEGER NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('draft', 'published', 'archived')),
    snapshot JSONB NOT NULL,
    created_by BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    published_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_roster_versions_status
    ON roster_versions(status);

CREATE UNIQUE INDEX IF NOT EXISTS ux_roster_versions_one_draft
    ON roster_versions(status)
    WHERE status = 'draft';

CREATE UNIQUE INDEX IF NOT EXISTS ux_roster_versions_one_published
    ON roster_versions(status)
    WHERE status = 'published';

-- New permissions used by the Draft/Publish workflow.
INSERT INTO permissions
    (permission_key, name, description, category, is_active)
VALUES
    ('roster.view', 'View Published Roster',
     'View the currently published roster.',
     'roster', TRUE),
    ('roster.draft.view', 'View Roster Draft',
     'View the private roster draft.',
     'roster', TRUE),
    ('roster.draft.edit', 'Edit Roster Draft',
     'Create and modify the private roster draft.',
     'roster', TRUE),
    ('roster.publish', 'Publish Roster',
     'Publish the current roster draft.',
     'roster', TRUE),
    ('roster.history.view', 'View Roster History',
     'View previously published roster versions and changes.',
     'roster', TRUE)
ON CONFLICT (permission_key) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    is_active = EXCLUDED.is_active;

-- Remove old roster permissions from the role matrix only if they exist,
-- then seed the new workflow permissions.
DELETE FROM role_permissions
WHERE permission_id IN (
    SELECT id
    FROM permissions
    WHERE permission_key IN (
        'roster.view',
        'roster.draft.view',
        'roster.draft.edit',
        'roster.publish',
        'roster.history.view'
    )
);

-- Admin: all five permissions.
INSERT INTO role_permissions (role, permission_id, allowed)
SELECT 'admin', id, TRUE
FROM permissions
WHERE permission_key IN (
    'roster.view',
    'roster.draft.view',
    'roster.draft.edit',
    'roster.publish',
    'roster.history.view'
);

-- Team Leader: full roster workflow.
INSERT INTO role_permissions (role, permission_id, allowed)
SELECT 'team_leader', id, TRUE
FROM permissions
WHERE permission_key IN (
    'roster.view',
    'roster.draft.view',
    'roster.draft.edit',
    'roster.publish',
    'roster.history.view'
);

-- Supervisor: full roster workflow.
INSERT INTO role_permissions (role, permission_id, allowed)
SELECT 'supervisor', id, TRUE
FROM permissions
WHERE permission_key IN (
    'roster.view',
    'roster.draft.view',
    'roster.draft.edit',
    'roster.publish',
    'roster.history.view'
);

-- Agent: published roster only.
INSERT INTO role_permissions (role, permission_id, allowed)
SELECT 'agent', id, TRUE
FROM permissions
WHERE permission_key = 'roster.view';

-- Bootstrap the existing Roster as Published Version 1.
-- This copies the current state into an immutable JSON snapshot.
INSERT INTO roster_versions (
    version_number,
    status,
    snapshot,
    created_by,
    published_by,
    published_at
)
SELECT
    1,
    'published',
    jsonb_build_object(
        'columns',
        COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', c.id,
                    'key', c.key,
                    'labelEn', c.label_en,
                    'labelFa', c.label_fa,
                    'color', c.color,
                    'textColor', c.text_color,
                    'isMulti', c.is_multi,
                    'isBuiltin', c.is_builtin,
                    'sortOrder', c.sort_order
                )
                ORDER BY c.sort_order
            )
            FROM roster_columns c
        ), '[]'::jsonb),

        'team',
        COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', m.id,
                    'fullName', m.full_name,
                    'username', m.username,
                    'isActive', m.is_active,
                    'userId', m.user_id
                )
                ORDER BY m.id
            )
            FROM team_members m
        ), '[]'::jsonb),

        'holidays',
        COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', h.id,
                    'date', h.holiday_date,
                    'label', h.label
                )
                ORDER BY h.holiday_date
            )
            FROM holidays h
        ), '[]'::jsonb),

        'entries',
        COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', re.id,
                    'date', re.entry_date,
                    'columnId', re.column_id,
                    'columnKey', c.key,
                    'freeText', re.free_text,
                    'memberIds',
                    COALESCE((
                        SELECT jsonb_agg(rem.team_member_id ORDER BY rem.team_member_id)
                        FROM roster_entry_members rem
                        WHERE rem.entry_id = re.id
                    ), '[]'::jsonb)
                )
                ORDER BY re.id
            )
            FROM roster_entries re
            JOIN roster_columns c ON c.id = re.column_id
        ), '[]'::jsonb)
    ),
    (SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1),
    (SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1),
    NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM roster_versions WHERE version_number = 1
);

COMMIT;
