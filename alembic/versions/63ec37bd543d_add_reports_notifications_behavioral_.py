"""add_reports_notifications_behavioral_subscriptions_tables

Revision ID: 63ec37bd543d
Revises: 31a2f094c5aa
Create Date: 2026-05-23 23:08:16.421204

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '63ec37bd543d'
down_revision = '31a2f094c5aa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # reports
    # ============================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            organization_id UUID REFERENCES organizations(id),
            job_id UUID REFERENCES jobs(id),
            case_id UUID REFERENCES cases(id),
            report_type VARCHAR(50) NOT NULL,
            format VARCHAR(20) NOT NULL,
            version VARCHAR(20) NOT NULL DEFAULT '1.0',
            status VARCHAR(20) NOT NULL DEFAULT 'generating',
            file_path VARCHAR(500),
            file_size_bytes BIGINT,
            generated_by_user_id UUID REFERENCES users(id),
            generated_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}',
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_reports_tenant_status ON reports (tenant_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reports_job ON reports (job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reports_case ON reports (case_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reports_generated_at ON reports (generated_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reports_tenant_type ON reports (tenant_id, report_type)")

    # ============================================================
    # notifications
    # ============================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES users(id),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            type VARCHAR(50) NOT NULL,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            related_job_id UUID REFERENCES jobs(id),
            related_case_id UUID REFERENCES cases(id),
            related_report_id UUID REFERENCES reports(id),
            channel VARCHAR(20) NOT NULL DEFAULT 'in_app',
            priority VARCHAR(20) NOT NULL DEFAULT 'normal',
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            read_at TIMESTAMPTZ,
            sent_at TIMESTAMPTZ,
            payload JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_status ON notifications (user_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_notifications_tenant_created ON notifications (tenant_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications (type)")

    # ============================================================
    # behavioral_sessions
    # ============================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS behavioral_sessions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            submission_id UUID NOT NULL REFERENCES submissions(id),
            job_id UUID NOT NULL REFERENCES jobs(id),
            user_id UUID REFERENCES users(id),
            session_id VARCHAR(100),
            keystroke_count INTEGER NOT NULL DEFAULT 0,
            paste_count INTEGER NOT NULL DEFAULT 0,
            focus_loss_count INTEGER NOT NULL DEFAULT 0,
            typing_speed_wpm DOUBLE PRECISION,
            risk_score NUMERIC(4,3),
            patterns JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_behavioral_sessions_submission ON behavioral_sessions (submission_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_behavioral_sessions_job ON behavioral_sessions (job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_behavioral_sessions_user ON behavioral_sessions (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_behavioral_sessions_risk ON behavioral_sessions (risk_score)")

    # ============================================================
    # tenant_subscriptions
    # ============================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_subscriptions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL UNIQUE REFERENCES tenants(id),
            plan VARCHAR(50) NOT NULL,
            status VARCHAR(20) NOT NULL,
            current_period_start TIMESTAMPTZ,
            current_period_end TIMESTAMPTZ,
            trial_end TIMESTAMPTZ,
            job_limit INTEGER,
            storage_limit_mb INTEGER,
            features JSONB NOT NULL DEFAULT '{}',
            stripe_customer_id VARCHAR(100),
            stripe_subscription_id VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_tenant_subscriptions_status ON tenant_subscriptions (status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_subscriptions")
    op.execute("DROP TABLE IF EXISTS behavioral_sessions")
    op.execute("DROP TABLE IF EXISTS notifications")
    op.execute("DROP TABLE IF EXISTS reports")
