-- Service Desk Hub
-- 003: Teams + Permissions
-- Safe migration: adds new management structures without deleting existing data.

BEGIN;

-- ============================================================
-- Link roster members to application users
-- Existing roster members are preserved.
-- user_id remains NULL until an existing member is linked to a user.
-- ============================================================

ALTER TABLE team_members
    ADD COLUMN IF NOT EXISTS user_id INTEGER;

CREATE UNIQUE INDEX IF NOT EXISTS idx_team_members_user_id
    ON team_members(user_id)
    WHERE user_id IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'team_members_user_id_fkey'
    ) THEN
        ALTER TABLE team_members
            ADD CONSTRAINT team_members_user_id_fkey
            FOREIGN KEY (user_id)
            REFERENCES users(id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- ============================================================
-- Teams
-- ============================================================

CREATE TABLE IF NOT EXISTS teams (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(120) NOT NULL UNIQUE,
    supervisor_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    description     TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_teams_supervisor
    ON teams(supervisor_id);

-- ============================================================
-- Team membership
-- Existing team_members are roster people, so keep that table.
-- This table connects those people to an actual Team.
-- ============================================================

CREATE TABLE IF NOT EXISTS team_assignments (
    team_id         INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    team_member_id  INTEGER NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (team_id, team_member_id)
);

CREATE INDEX IF NOT EXISTS idx_team_assignments_member
    ON team_assignments(team_member_id);

-- ============================================================
-- Permission catalog
-- ============================================================

CREATE TABLE IF NOT EXISTS permissions (
    id              SERIAL PRIMARY KEY,
    permission_key  VARCHAR(100) NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    description     TEXT,
    category        VARCHAR(60) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================
-- Role permissions
-- ============================================================

CREATE TABLE IF NOT EXISTS role_permissions (
    role            VARCHAR(20) NOT NULL
                    CHECK (role IN ('admin','leadership','supervisor','agent')),
    permission_id   INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    allowed         BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (role, permission_id)
);

-- ============================================================
-- User-specific permission overrides
-- allowed = TRUE  -> explicitly grant
-- allowed = FALSE -> explicitly deny
-- ============================================================

CREATE TABLE IF NOT EXISTS user_permission_overrides (
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_id   INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    allowed         BOOLEAN NOT NULL,
    PRIMARY KEY (user_id, permission_id)
);

-- ============================================================
-- Seed permission catalog
-- ============================================================

INSERT INTO permissions
    (permission_key, name, description, category)
VALUES
    ('dashboard.view', 'View Dashboard', 'Access the Service Desk Dashboard', 'Dashboard'),

    ('users.view', 'View Users', 'View application users', 'Users'),
    ('users.create', 'Create Users', 'Create application users', 'Users'),
    ('users.edit', 'Edit Users', 'Edit application users', 'Users'),
    ('users.disable', 'Disable Users', 'Activate or deactivate users', 'Users'),

    ('roles.view', 'View Roles & Permissions', 'View role permission configuration', 'Roles'),
    ('roles.manage', 'Manage Roles & Permissions', 'Change role permissions', 'Roles'),

    ('teams.view', 'View Teams', 'View teams and members', 'Teams'),
    ('teams.create', 'Create Teams', 'Create new teams', 'Teams'),
    ('teams.edit', 'Edit Teams', 'Edit team details', 'Teams'),
    ('teams.delete', 'Delete Teams', 'Delete teams', 'Teams'),
    ('teams.members.manage', 'Manage Team Members', 'Add or remove agents from teams', 'Teams'),

    ('roster.view', 'View Roster', 'View roster information', 'Roster'),
    ('roster.edit', 'Edit Roster', 'Assign and remove roster members', 'Roster'),
    ('roster.manage', 'Manage Roster', 'Full roster administration', 'Roster'),

    ('shifts.view', 'View Shifts', 'View roster shift definitions', 'Shifts'),
    ('shifts.manage', 'Manage Shifts', 'Create, edit and remove shifts', 'Shifts'),

    ('holidays.view', 'View Holidays', 'View configured holidays', 'Holidays'),
    ('holidays.manage', 'Manage Holidays', 'Create and remove holidays', 'Holidays'),

    ('reports.view', 'View Reports', 'View operational reports', 'Reports'),
    ('reports.save', 'Save Reports', 'Save report history to the database', 'Reports'),

    ('audit.view', 'View Audit Logs', 'View system audit activity', 'Audit'),

    ('settings.view', 'View System Settings', 'View system settings', 'Settings'),
    ('settings.manage', 'Manage System Settings', 'Change system settings', 'Settings')
ON CONFLICT (permission_key) DO NOTHING;

-- ============================================================
-- Default role permissions
--
-- Admin is treated as full-access by the backend authorization
-- layer. These rows also make the configuration visible in the UI.
-- ============================================================

INSERT INTO role_permissions (role, permission_id, allowed)
SELECT 'admin', id, TRUE
FROM permissions
ON CONFLICT (role, permission_id) DO UPDATE SET allowed = TRUE;

-- Leadership
INSERT INTO role_permissions (role, permission_id, allowed)
SELECT 'leadership', id, TRUE
FROM permissions
WHERE permission_key IN (
    'dashboard.view',
    'roles.view',
    'teams.view',
    'teams.create',
    'teams.edit',
    'teams.members.manage',
    'roster.view',
    'roster.edit',
    'roster.manage',
    'shifts.view',
    'shifts.manage',
    'holidays.view',
    'holidays.manage',
    'reports.view',
    'reports.save',
    'audit.view'
)
ON CONFLICT (role, permission_id) DO UPDATE SET allowed = TRUE;

-- Supervisor
INSERT INTO role_permissions (role, permission_id, allowed)
SELECT 'supervisor', id, TRUE
FROM permissions
WHERE permission_key IN (
    'dashboard.view',
    'teams.view',
    'teams.edit',
    'teams.members.manage',
    'roster.view',
    'roster.edit',
    'shifts.view',
    'reports.view'
)
ON CONFLICT (role, permission_id) DO UPDATE SET allowed = TRUE;

-- Agent
INSERT INTO role_permissions (role, permission_id, allowed)
SELECT 'agent', id, TRUE
FROM permissions
WHERE permission_key IN (
    'dashboard.view',
    'roster.view',
    'reports.view'
)
ON CONFLICT (role, permission_id) DO UPDATE SET allowed = TRUE;

COMMIT;
