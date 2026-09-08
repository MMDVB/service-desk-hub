"""ORM models. These map to the tables created by sql/schema.sql — the schema
is the source of truth (created once with psql), SQLAlchemy just describes it
here so Python code can query/insert without writing raw SQL everywhere."""
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, Date, DateTime, ForeignKey,
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
    role = Column(String(20), nullable=False, default="agent")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('admin','leadership','agent')", name="users_role_check"),
    )


class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    username = Column(String(80))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


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
