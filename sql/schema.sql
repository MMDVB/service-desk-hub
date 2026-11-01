-- ============================================================
-- Service Desk Hub — Database Schema (PostgreSQL)
-- Fresh-install schema matching the current application model.
-- ============================================================

BEGIN;

-- ---------- Users & roles ----------
CREATE TABLE users (
  id            SERIAL PRIMARY KEY,
  username      VARCHAR(80) UNIQUE NOT NULL,
  display_name  VARCHAR(120) NOT NULL,
  password_hash TEXT,
  ad_username   VARCHAR(120) UNIQUE,
  role          VARCHAR(20) NOT NULL DEFAULT 'engineer'
                  CHECK (role IN ('admin','team_leader','supervisor','engineer')),
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Team members ----------
CREATE TABLE team_members (
  id          SERIAL PRIMARY KEY,
  full_name   VARCHAR(120) NOT NULL,
  username    VARCHAR(80),
  is_active   BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX idx_team_members_user_id
  ON team_members(user_id)
  WHERE user_id IS NOT NULL;

-- ---------- Teams ----------
CREATE TABLE teams (
  id            SERIAL PRIMARY KEY,
  name          VARCHAR(120) UNIQUE NOT NULL,
  supervisor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  description   TEXT,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_teams_supervisor
  ON teams(supervisor_id);

-- ---------- Team assignments ----------
CREATE TABLE team_assignments (
  team_id       INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  team_member_id INTEGER NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
  assigned_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (team_id, team_member_id)
);

CREATE UNIQUE INDEX uq_team_assignments_member
  ON team_assignments(team_member_id);


-- ---------- Permissions ----------
CREATE TABLE permissions (
  id             SERIAL PRIMARY KEY,
  permission_key VARCHAR(100) UNIQUE NOT NULL,
  name           VARCHAR(120) NOT NULL,
  description    TEXT,
  category       VARCHAR(60) NOT NULL,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE
);

-- ---------- Role permissions ----------
CREATE TABLE role_permissions (
  role          VARCHAR(20) NOT NULL,
  permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
  allowed       BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (role, permission_id),
  CONSTRAINT role_permissions_role_check
    CHECK (role IN ('admin','team_leader','supervisor','engineer'))
);

-- ---------- Per-user permission overrides ----------
CREATE TABLE user_permission_overrides (
  user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  permission_id  INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
  allowed        BOOLEAN NOT NULL,
  PRIMARY KEY (user_id, permission_id)
);

-- ---------- Permission seed ----------
INSERT INTO permissions
  (id, permission_key, name, description, category, is_active)
VALUES
  (1, 'dashboard.view', 'View Dashboard',
   'Access the Service Desk Dashboard', 'Dashboard', TRUE),

  (2, 'users.view', 'View Users',
   'View application users', 'Users', TRUE),

  (3, 'users.create', 'Create Users',
   'Create application users', 'Users', TRUE),

  (4, 'users.edit', 'Edit Users',
   'Edit application users', 'Users', TRUE),

  (5, 'users.disable', 'Disable Users',
   'Activate or deactivate users', 'Users', TRUE),

  (6, 'roles.view', 'View Roles & Permissions',
   'View role permission configuration', 'Roles', TRUE),

  (7, 'roles.manage', 'Manage Roles & Permissions',
   'Change role permissions', 'Roles', TRUE),

  (8, 'teams.view', 'View Teams',
   'View teams and members', 'Teams', TRUE),

  (9, 'teams.create', 'Create Teams',
   'Create new teams', 'Teams', TRUE),

  (10, 'teams.edit', 'Edit Teams',
   'Edit team details', 'Teams', TRUE),

  (11, 'teams.delete', 'Delete Teams',
   'Delete teams', 'Teams', TRUE),

  (12, 'teams.members.manage', 'Manage Team Members',
   'Add or remove engineers from teams', 'Teams', TRUE),

  (13, 'roster.view', 'View Published Roster',
   'View the currently published roster.', 'roster', TRUE),

  (14, 'roster.edit', 'Edit Roster',
   'Assign and remove roster members', 'Roster', TRUE),

  (15, 'roster.manage', 'Manage Roster',
   'Full roster administration', 'Roster', TRUE),

  (16, 'shifts.view', 'View Shifts',
   'View roster shift definitions', 'Shifts', TRUE),

  (17, 'shifts.manage', 'Manage Shifts',
   'Create, edit and remove shifts', 'Shifts', TRUE),

  (18, 'holidays.view', 'View Holidays',
   'View configured holidays', 'Holidays', TRUE),

  (19, 'holidays.manage', 'Manage Holidays',
   'Create and remove holidays', 'Holidays', TRUE),

  (20, 'reports.view', 'View Reports',
   'View operational reports', 'Reports', TRUE),

  (21, 'reports.save', 'Save Reports',
   'Save report history to the database', 'Reports', TRUE),

  (22, 'audit.view', 'View Audit Logs',
   'View system audit activity', 'Audit', TRUE),

  (23, 'settings.view', 'View System Settings',
   'View system settings', 'Settings', TRUE),

  (24, 'settings.manage', 'Manage System Settings',
   'Change system settings', 'Settings', TRUE),

  (26, 'roster.draft.view', 'View Roster Draft',
   'View the private roster draft.', 'roster', TRUE),

  (27, 'roster.draft.edit', 'Edit Roster Draft',
   'Create and modify the private roster draft.', 'roster', TRUE),

  (28, 'roster.publish', 'Publish Roster',
   'Publish the current roster draft.', 'roster', TRUE),

  (29, 'roster.history.view', 'View Roster History',
   'View previously published roster versions and changes.', 'roster', TRUE);

-- Keep the sequence aligned with the explicit permission IDs above.
SELECT setval(
  pg_get_serial_sequence('permissions', 'id'),
  (SELECT MAX(id) FROM permissions)
);

-- ---------- Role permission matrix ----------

-- Admin: all 28 permissions.
INSERT INTO role_permissions (role, permission_id, allowed)
SELECT 'admin', id, TRUE
FROM permissions;

-- Team Leader: 21 rows; settings.view explicitly denied.
INSERT INTO role_permissions (role, permission_id, allowed)
SELECT
  'team_leader',
  id,
  CASE WHEN permission_key = 'settings.view' THEN FALSE ELSE TRUE END
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
  'audit.view',
  'settings.view',
  'roster.draft.view',
  'roster.draft.edit',
  'roster.publish',
  'roster.history.view'
);

-- Supervisor: 12 permissions.
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
  'reports.view',
  'roster.draft.view',
  'roster.draft.edit',
  'roster.publish',
  'roster.history.view'
);

-- Engineer: published roster/report/dashboard access only.
INSERT INTO role_permissions (role, permission_id, allowed)
SELECT 'engineer', id, TRUE
FROM permissions
WHERE permission_key IN (
  'dashboard.view',
  'roster.view',
  'reports.view'
);


-- ---------- Roster columns ----------
CREATE TABLE roster_columns (
  id         SERIAL PRIMARY KEY,
  key        VARCHAR(60) UNIQUE NOT NULL,
  label_en   VARCHAR(120) NOT NULL,
  label_fa   VARCHAR(120) NOT NULL,
  color      VARCHAR(20) NOT NULL DEFAULT '#DBEAFE',
  text_color VARCHAR(20) NOT NULL DEFAULT '#1D4ED8',
  is_multi   BOOLEAN NOT NULL DEFAULT TRUE,
  is_builtin BOOLEAN NOT NULL DEFAULT FALSE,
  sort_order INTEGER NOT NULL DEFAULT 0
);

-- ---------- Roster entries ----------
CREATE TABLE roster_entries (
  id         SERIAL PRIMARY KEY,
  entry_date DATE NOT NULL,
  column_id  INTEGER NOT NULL REFERENCES roster_columns(id) ON DELETE CASCADE,
  free_text  TEXT,
  UNIQUE (entry_date, column_id, free_text)
);

-- ---------- Roster entry members ----------
CREATE TABLE roster_entry_members (
  entry_id       INTEGER NOT NULL REFERENCES roster_entries(id) ON DELETE CASCADE,
  team_member_id INTEGER NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
  PRIMARY KEY (entry_id, team_member_id)
);

CREATE INDEX idx_roster_entries_date
  ON roster_entries(entry_date);

-- ---------- Roster versions / Draft & Publish ----------
CREATE TABLE roster_versions (
  id             BIGSERIAL PRIMARY KEY,
  version_number INTEGER NOT NULL UNIQUE,
  status         VARCHAR(20) NOT NULL
                   CHECK (status IN ('draft','published','archived')),
  snapshot       JSONB NOT NULL,
  created_by     BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_by   BIGINT REFERENCES users(id) ON DELETE SET NULL,
  published_at   TIMESTAMPTZ,
  updated_by     BIGINT REFERENCES users(id) ON DELETE SET NULL,
  updated_at     TIMESTAMPTZ
);

CREATE INDEX ix_roster_versions_status
  ON roster_versions(status);

CREATE INDEX ix_roster_versions_updated_by
  ON roster_versions(updated_by);

CREATE UNIQUE INDEX ux_roster_versions_one_draft
  ON roster_versions(status)
  WHERE status = 'draft';

CREATE UNIQUE INDEX ux_roster_versions_one_published
  ON roster_versions(status)
  WHERE status = 'published';


-- ---------- Official holidays ----------
CREATE TABLE holidays (
  id           SERIAL PRIMARY KEY,
  holiday_date DATE UNIQUE NOT NULL,
  label        VARCHAR(120) NOT NULL
);

-- ---------- Audit log ----------
CREATE TABLE audit_log (
  id         SERIAL PRIMARY KEY,
  user_id    INTEGER REFERENCES users(id),
  action     VARCHAR(60) NOT NULL,
  detail     JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_log_created_at
  ON audit_log(created_at);

-- ---------- Report history ----------
CREATE TABLE sdcm_reports (
  id          SERIAL PRIMARY KEY,
  report_date DATE NOT NULL,
  uploaded_by INTEGER REFERENCES users(id),
  summary     JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (report_date)
);

CREATE TABLE aicc_reports (
  id          SERIAL PRIMARY KEY,
  report_date DATE NOT NULL,
  uploaded_by INTEGER REFERENCES users(id),
  summary     JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (report_date)
);

CREATE TABLE sla_reports (
  id          SERIAL PRIMARY KEY,
  report_date DATE NOT NULL,
  uploaded_by INTEGER REFERENCES users(id),
  summary     JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (report_date)
);

CREATE INDEX idx_sdcm_reports_date
  ON sdcm_reports(report_date);

CREATE INDEX idx_aicc_reports_date
  ON aicc_reports(report_date);

CREATE INDEX idx_sla_reports_date
  ON sla_reports(report_date);


-- ---------- Default roster columns ----------
INSERT INTO roster_columns
  (key, label_en, label_fa, color, text_color, is_multi, is_builtin, sort_order)
VALUES
  ('day1',         'Day_1 (07:00-19:00)',     'روز_۱ (۰۷:۰۰-۱۹:۰۰)',   '#DBEAFE', '#1D4ED8', TRUE,  TRUE, 1),
  ('day2',         'Day_2 (07:00-19:00)',     'روز_۲ (۰۷:۰۰-۱۹:۰۰)',   '#DBEAFE', '#1D4ED8', TRUE,  TRUE, 2),
  ('hq',           'Day - HQ Office (08-17)', 'حضور HQ (۰۸:۰۰-۱۷:۰۰)', '#FEF9C3', '#854D0E', TRUE,  TRUE, 3),
  ('night1',       'Night_1 (19:00-07:00)',   'شب_۱ (۱۹:۰۰-۰۷:۰۰)',    '#E0E7FF', '#3730A3', TRUE,  TRUE, 4),
  ('night2',       'Night_2 (19:00-07:00)',   'شب_۲ (۱۹:۰۰-۰۷:۰۰)',    '#E0E7FF', '#3730A3', TRUE,  TRUE, 5),
  ('oncall',       'Leadership On-Call',      'آنکال لیدرشیپ',         '#CCFBF1', '#0F766E', FALSE, TRUE, 6),
  ('off',          'Off',                     'آف',                    '#E9D5FF', '#6B21A8', TRUE,  TRUE, 7),
  ('leaveRequest', 'Leave Request',           'درخواست مرخصی',         '#FBCFE8', '#9D174D', TRUE,  TRUE, 8),
  ('cab',          'CAB',                     'CAB',                   '#E2E8F0', '#334155', TRUE,  TRUE, 9);

-- ---------- First admin account ----------
-- Password is set by scripts/create_admin.js.
-- Never store a plain-text default password in this schema.

COMMIT;
