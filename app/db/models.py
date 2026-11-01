"""ORM models. These map to the tables created by sql/schema.sql — the schema
is the source of truth (created once with psql), SQLAlchemy just describes it
here so Python code can query/insert without writing raw SQL everywhere."""
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, Text, Date, Time, DateTime, ForeignKey,
    UniqueConstraint, CheckConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from .session import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    display_name = Column(String(120), nullable=False)
    password_hash = Column(Text)
    ad_username = Column(String(120), unique=True)
    role = Column(String(20), nullable=False, default="engineer")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('admin','team_leader','supervisor','engineer')", name="users_role_check"),
    )


class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    username = Column(String(80))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    user = relationship("User")


class RosterColumn(Base):
    __tablename__ = "roster_columns"
    id = Column(Integer, primary_key=True)
    key = Column(String(60), unique=True, nullable=False)
    label_en = Column(String(120), nullable=False)
    label_fa = Column(String(120), nullable=False)
    color = Column(String(20), nullable=False, default="#DBEAFE")
    text_color = Column(String(20), nullable=False, default="#1D4ED8")
    is_multi = Column(Boolean, nullable=False, default=True)
    is_builtin = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)


class RosterEntry(Base):
    __tablename__ = "roster_entries"
    id = Column(Integer, primary_key=True)
    entry_date = Column(Date, nullable=False)
    column_id = Column(Integer, ForeignKey("roster_columns.id", ondelete="CASCADE"), nullable=False)
    free_text = Column(Text)

    members = relationship("RosterEntryMember", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("entry_date", "column_id", "free_text", name="roster_entries_unique"),
    )


class RosterEntryMember(Base):
    __tablename__ = "roster_entry_members"
    entry_id = Column(Integer, ForeignKey("roster_entries.id", ondelete="CASCADE"), primary_key=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id", ondelete="CASCADE"), primary_key=True)

    team_member = relationship("TeamMember")


class Holiday(Base):
    __tablename__ = "holidays"
    id = Column(Integer, primary_key=True)
    holiday_date = Column(Date, unique=True, nullable=False)
    label = Column(String(120), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(60), nullable=False)
    detail = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SdcmReport(Base):
    __tablename__ = "sdcm_reports"
    id = Column(Integer, primary_key=True)
    report_date = Column(Date, unique=True, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    summary = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AiccReport(Base):
    __tablename__ = "aicc_reports"
    id = Column(Integer, primary_key=True)
    report_date = Column(Date, unique=True, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    summary = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SlaReport(Base):
    __tablename__ = "sla_reports"
    id = Column(Integer, primary_key=True)
    report_date = Column(Date, unique=True, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    summary = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    supervisor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    description = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    supervisor = relationship("User", foreign_keys=[supervisor_id])


class TeamAssignment(Base):
    __tablename__ = "team_assignments"

    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    team_member_id = Column(
        Integer,
        ForeignKey("team_members.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())

    team = relationship("Team")
    team_member = relationship("TeamMember")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    permission_key = Column(String(100), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text)
    category = Column(String(60), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role = Column(String(20), primary_key=True)
    permission_id = Column(
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    allowed = Column(Boolean, nullable=False, default=True)

    permission = relationship("Permission")


class UserPermissionOverride(Base):
    __tablename__ = "user_permission_overrides"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id = Column(
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    allowed = Column(Boolean, nullable=False)

    permission = relationship("Permission")
class RosterVersion(Base):
    __tablename__ = "roster_versions"

    id = Column(Integer, primary_key=True)
    version_number = Column(Integer, nullable=False, unique=True)
    status = Column(String(20), nullable=False)
    snapshot = Column(JSONB, nullable=False)

    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    published_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    published_at = Column(DateTime(timezone=True))

    updated_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    updated_at = Column(
        DateTime(timezone=True),
    )

    creator = relationship(
        "User",
        foreign_keys=[created_by],
    )

    updater = relationship(
        "User",
        foreign_keys=[updated_by],
    )

    publisher = relationship(
        "User",
        foreign_keys=[published_by],
    )


class OnCallUpload(Base):
    __tablename__ = "oncall_uploads"

    id = Column(Integer, primary_key=True)
    file_key = Column(String(191), nullable=False)
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(150), nullable=False, default="")
    source_type = Column(String(30), nullable=False)
    source_group = Column(String(100), nullable=False)
    period_start = Column(Date)
    period_end = Column(Date)
    rows_count = Column(Integer, nullable=False, default=0)
    file_sha256 = Column(String(64), nullable=False, default="")
    report = Column(JSONB)
    is_current = Column(Boolean, nullable=False, default=True)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    uploader = relationship("User")
    entries = relationship(
        "OnCallEntry",
        back_populates="upload",
        cascade="all, delete-orphan",
    )


class OnCallEntry(Base):
    __tablename__ = "oncall_entries"

    id = Column(BigInteger, primary_key=True)
    upload_id = Column(
        Integer,
        ForeignKey("oncall_uploads.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_group = Column(String(100), nullable=False)
    team = Column(String(150), nullable=False)
    duty_date = Column(Date, nullable=False)
    shift_start = Column(Time)
    shift_end = Column(Time)
    person_name = Column(String(150), nullable=False, default="")
    role = Column(String(50), nullable=False, default="")
    phone = Column(String(30), nullable=False, default="")
    email = Column(String(150), nullable=False, default="")
    note = Column(String(255), nullable=False, default="")
    is_superseded = Column(Boolean, nullable=False, default=False)

    upload = relationship("OnCallUpload", back_populates="entries")


class OnCallSetting(Base):
    __tablename__ = "oncall_settings"

    setting_key = Column(String(100), primary_key=True)
    setting_value = Column(JSONB, nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    updater = relationship("User")
