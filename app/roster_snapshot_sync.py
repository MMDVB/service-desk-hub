from sqlalchemy import text
from sqlalchemy.orm import Session


def deactivate_member_in_snapshots(db: Session, member_id: int) -> None:
    db.execute(
        text("""
            UPDATE roster_versions AS rv
            SET snapshot = jsonb_set(
                rv.snapshot,
                '{team}',
                (
                    SELECT COALESCE(
                        jsonb_agg(
                            CASE
                                WHEN member->>'id' = CAST(:member_id AS TEXT)
                                THEN jsonb_set(
                                    member,
                                    '{isActive}',
                                    'false'::jsonb,
                                    true
                                )
                                ELSE member
                            END
                            ORDER BY ord
                        ),
                        '[]'::jsonb
                    )
                    FROM jsonb_array_elements(
                        COALESCE(rv.snapshot->'team', '[]'::jsonb)
                    ) WITH ORDINALITY AS items(member, ord)
                ),
                true
            )
            WHERE jsonb_typeof(rv.snapshot->'team') = 'array'
              AND EXISTS (
                  SELECT 1
                  FROM jsonb_array_elements(rv.snapshot->'team') AS items(member)
                  WHERE member->>'id' = CAST(:member_id AS TEXT)
              )
        """),
        {"member_id": member_id},
    )
