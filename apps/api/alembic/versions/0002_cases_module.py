"""Week 3: Cases module - all tables, indexes, and constraints.

Revision ID: 0002_cases_module
Revises: 0001_baseline
Create Date: 2025-12-13

Creates:
- cases (with soft delete, unique constraints, indexes)
- case_status_history
- case_notes
- tasks
- meta_leads
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002_cases_module'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # meta_leads (create first due to FK from cases)
    # ==========================================================================
    op.create_table(
        'meta_leads',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('meta_lead_id', sa.String(100), nullable=False),
        sa.Column('meta_form_id', sa.String(100), nullable=True),
        sa.Column('meta_page_id', sa.String(100), nullable=True),
        sa.Column('field_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_converted', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('converted_case_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('conversion_error', sa.Text(), nullable=True),
        sa.Column('meta_created_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('converted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'meta_lead_id', name='uq_meta_lead'),
    )
    
    op.create_index(
        'idx_meta_unconverted',
        'meta_leads',
        ['organization_id'],
        postgresql_where=sa.text('is_converted = FALSE'),
    )
    
    # ==========================================================================
    # cases
    # ==========================================================================
    op.create_table(
        'cases',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('case_number', sa.String(10), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Workflow
        sa.Column('status', sa.String(50), server_default=sa.text("'new_unread'"), nullable=False),
        sa.Column('source', sa.String(20), server_default=sa.text("'manual'"), nullable=False),
        sa.Column('assigned_to_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('meta_lead_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Contact
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('email', postgresql.CITEXT(), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('state', sa.String(2), nullable=True),
        
        # Demographics
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('race', sa.String(100), nullable=True),
        sa.Column('height_ft', sa.Numeric(3, 1), nullable=True),
        sa.Column('weight_lb', sa.Integer(), nullable=True),
        
        # Eligibility
        sa.Column('is_age_eligible', sa.Boolean(), nullable=True),
        sa.Column('is_citizen_or_pr', sa.Boolean(), nullable=True),
        sa.Column('has_child', sa.Boolean(), nullable=True),
        sa.Column('is_non_smoker', sa.Boolean(), nullable=True),
        sa.Column('has_surrogate_experience', sa.Boolean(), nullable=True),
        sa.Column('num_deliveries', sa.Integer(), nullable=True),
        sa.Column('num_csections', sa.Integer(), nullable=True),
        
        # Soft delete
        sa.Column('is_archived', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        # Constraints
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['archived_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['meta_lead_id'], ['meta_leads.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'case_number', name='uq_case_number'),
    )
    
    # Partial unique: email unique per org for active cases only
    op.create_index(
        'uq_case_email_active',
        'cases',
        ['organization_id', 'email'],
        unique=True,
        postgresql_where=sa.text('is_archived = FALSE'),
    )
    
    # Query optimization indexes
    op.create_index('idx_cases_org_status', 'cases', ['organization_id', 'status'])
    op.create_index('idx_cases_org_assigned', 'cases', ['organization_id', 'assigned_to_user_id'])
    op.create_index('idx_cases_org_created', 'cases', ['organization_id', 'created_at'])
    op.create_index(
        'idx_cases_org_active',
        'cases',
        ['organization_id'],
        postgresql_where=sa.text('is_archived = FALSE'),
    )
    
    # Add FK from meta_leads.converted_case_id back to cases
    op.create_foreign_key(
        'fk_meta_leads_converted_case',
        'meta_leads', 'cases',
        ['converted_case_id'], ['id'],
        ondelete='SET NULL',
    )
    
    # ==========================================================================
    # case_status_history
    # ==========================================================================
    op.create_table(
        'case_status_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_status', sa.String(50), nullable=False),
        sa.Column('to_status', sa.String(50), nullable=False),
        sa.Column('changed_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    op.create_index('idx_case_history_case', 'case_status_history', ['case_id', 'changed_at'])
    
    # ==========================================================================
    # case_notes
    # ==========================================================================
    op.create_table(
        'case_notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    op.create_index('idx_case_notes_case', 'case_notes', ['case_id', 'created_at'])
    
    # ==========================================================================
    # tasks
    # ==========================================================================
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('assigned_to_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('task_type', sa.String(50), server_default=sa.text("'other'"), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('due_time', sa.Time(), nullable=True),
        sa.Column('is_completed', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['completed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    op.create_index('idx_tasks_org_assigned', 'tasks', ['organization_id', 'assigned_to_user_id', 'is_completed'])
    op.create_index(
        'idx_tasks_due',
        'tasks',
        ['organization_id', 'due_date'],
        postgresql_where=sa.text('is_completed = FALSE'),
    )
    
    # ==========================================================================
    # Trigger for updated_at auto-update on cases and tasks
    # ==========================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    op.execute("""
        CREATE TRIGGER update_cases_updated_at
            BEFORE UPDATE ON cases
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_tasks_updated_at
            BEFORE UPDATE ON tasks
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Drop triggers (but not the shared function - it's used by baseline migration)
    op.execute("DROP TRIGGER IF EXISTS update_tasks_updated_at ON tasks")
    op.execute("DROP TRIGGER IF EXISTS update_cases_updated_at ON cases")
    # Note: NOT dropping update_updated_at_column() as it's shared with baseline
    
    # Drop tables in reverse order
    op.drop_table('tasks')
    op.drop_table('case_notes')
    op.drop_table('case_status_history')
    
    # Drop FK from meta_leads before dropping cases
    op.drop_constraint('fk_meta_leads_converted_case', 'meta_leads', type_='foreignkey')
    
    op.drop_table('cases')
    op.drop_table('meta_leads')

