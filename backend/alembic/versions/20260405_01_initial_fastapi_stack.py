"""initial fastapi stack"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260405_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    session_kind = sa.Enum("jd", "resume", "interview", name="session_kind")
    message_role = sa.Enum("user", "assistant", name="message_role")
    analysis_source_type = sa.Enum("jd", "resume", name="analysis_source_type")
    job_type = sa.Enum(
        "jd_analyze",
        "resume_optimize",
        "interview_start",
        "interview_continue",
        name="job_type",
    )
    job_status = sa.Enum("queued", "running", "succeeded", "failed", name="job_status")

    bind = op.get_bind()
    session_kind.create(bind, checkfirst=True)
    message_role.create(bind, checkfirst=True)
    analysis_source_type.create(bind, checkfirst=True)
    job_type.create(bind, checkfirst=True)
    job_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("session_kind", session_kind, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"], unique=False)
    op.create_index(
        "ix_chat_sessions_user_kind_created",
        "chat_sessions",
        ["user_id", "session_kind", "created_at"],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.BigInteger(), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"], unique=False)
    op.create_index(
        "ix_chat_messages_session_created",
        "chat_messages",
        ["session_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.BigInteger(), sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_type", analysis_source_type, nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("structured_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_analysis_results_user_id", "analysis_results", ["user_id"], unique=False)
    op.create_index(
        "ix_analysis_results_user_source_created",
        "analysis_results",
        ["user_id", "source_type", "created_at"],
        unique=False,
    )

    op.create_table(
        "job_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.BigInteger(), sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_type", job_type, nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_job_records_job_type", "job_records", ["job_type"], unique=False)
    op.create_index("ix_job_records_user_id", "job_records", ["user_id"], unique=False)
    op.create_index(
        "ix_job_records_user_status_created",
        "job_records",
        ["user_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_job_records_session_created",
        "job_records",
        ["session_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_job_records_session_created", table_name="job_records")
    op.drop_index("ix_job_records_user_status_created", table_name="job_records")
    op.drop_index("ix_job_records_user_id", table_name="job_records")
    op.drop_index("ix_job_records_job_type", table_name="job_records")
    op.drop_table("job_records")

    op.drop_index("ix_analysis_results_user_source_created", table_name="analysis_results")
    op.drop_index("ix_analysis_results_user_id", table_name="analysis_results")
    op.drop_table("analysis_results")

    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_chat_sessions_user_kind_created", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    sa.Enum(name="job_status").drop(bind, checkfirst=True)
    sa.Enum(name="job_type").drop(bind, checkfirst=True)
    sa.Enum(name="analysis_source_type").drop(bind, checkfirst=True)
    sa.Enum(name="message_role").drop(bind, checkfirst=True)
    sa.Enum(name="session_kind").drop(bind, checkfirst=True)
