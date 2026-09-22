BEGIN;

-- =========================================================
-- 1. Allow the new role vocabulary in role_permissions
-- =========================================================

ALTER TABLE role_permissions
    DROP CONSTRAINT IF EXISTS role_permissions_role_check;

ALTER TABLE role_permissions
    ADD CONSTRAINT role_permissions_role_check
    CHECK (
        role IN ('admin', 'team_leader', 'supervisor', 'agent', 'leadership')
    );


-- =========================================================
-- 2. Convert old Leadership users to Supervisor
-- =========================================================

UPDATE users
SET role = 'supervisor'
WHERE role = 'leadership';


-- =========================================================
-- 3. Copy Leadership permissions to Team Leader
-- =========================================================

INSERT INTO role_permissions (role, permission_id, allowed)
SELECT
    'team_leader',
    permission_id,
    allowed
FROM role_permissions
WHERE role = 'leadership'
ON CONFLICT (role, permission_id)
DO UPDATE SET allowed = EXCLUDED.allowed;


-- =========================================================
-- 4. Remove old Leadership permission rows
-- =========================================================

DELETE FROM role_permissions
WHERE role = 'leadership';


-- =========================================================
-- 5. Final role constraint for users
-- =========================================================

ALTER TABLE users
    DROP CONSTRAINT IF EXISTS users_role_check;

ALTER TABLE users
    ADD CONSTRAINT users_role_check
    CHECK (
        role IN ('admin', 'team_leader', 'supervisor', 'agent')
    );


-- =========================================================
-- 6. Final role constraint for role_permissions
-- =========================================================

ALTER TABLE role_permissions
    DROP CONSTRAINT IF EXISTS role_permissions_role_check;

ALTER TABLE role_permissions
    ADD CONSTRAINT role_permissions_role_check
    CHECK (
        role IN ('admin', 'team_leader', 'supervisor', 'agent')
    );


COMMIT;
