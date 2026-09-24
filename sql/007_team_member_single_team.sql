-- Enforce one active team assignment per TeamMember.
-- Each TeamMember can belong to only one Team.

CREATE UNIQUE INDEX IF NOT EXISTS uq_team_assignments_member
  ON team_assignments(team_member_id);
