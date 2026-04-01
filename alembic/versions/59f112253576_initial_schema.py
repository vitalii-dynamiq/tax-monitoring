"""initial schema

Revision ID: 59f112253576
Revises:
Create Date: 2026-03-12 04:49:52.988540
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '59f112253576'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('audit_log',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('entity_type', sa.Text(), nullable=False),
    sa.Column('entity_id', sa.BigInteger(), nullable=False),
    sa.Column('action', sa.Text(), nullable=False),
    sa.Column('old_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('new_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('changed_by', sa.Text(), nullable=False),
    sa.Column('change_source', sa.Text(), nullable=False),
    sa.Column('change_reason', sa.Text(), nullable=True),
    sa.Column('source_reference', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_entity', 'audit_log', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_audit_source', 'audit_log', ['change_source'], unique=False)
    op.create_index('idx_audit_time', 'audit_log', ['created_at'], unique=False)

    op.create_table('jurisdictions',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('local_name', sa.Text(), nullable=True),
    sa.Column('jurisdiction_type', sa.Text(), nullable=False),
    sa.Column('path', sa.Text(), nullable=False),
    sa.Column('parent_id', sa.BigInteger(), nullable=True),
    sa.Column('country_code', sa.Text(), nullable=False),
    sa.Column('subdivision_code', sa.Text(), nullable=True),
    sa.Column('timezone', sa.Text(), nullable=True),
    sa.Column('currency_code', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['parent_id'], ['jurisdictions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_index('idx_jurisdictions_country', 'jurisdictions', ['country_code'], unique=False)
    op.create_index('idx_jurisdictions_type', 'jurisdictions', ['jurisdiction_type'], unique=False)
    op.create_index(op.f('ix_jurisdictions_parent_id'), 'jurisdictions', ['parent_id'], unique=False)

    op.create_table('property_classifications',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('local_mappings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )

    op.create_table('tax_categories',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('level_0', sa.Text(), nullable=False),
    sa.Column('level_1', sa.Text(), nullable=False),
    sa.Column('level_2', sa.Text(), nullable=False),
    sa.Column('base_type', sa.Text(), nullable=False),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )

    op.create_table('monitored_sources',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('jurisdiction_id', sa.BigInteger(), nullable=True),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('source_type', sa.Text(), nullable=False),
    sa.Column('language', sa.Text(), nullable=False),
    sa.Column('check_frequency_days', sa.Integer(), nullable=False),
    sa.Column('last_checked_at', sa.DateTime(), nullable=True),
    sa.Column('last_content_hash', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['jurisdiction_id'], ['jurisdictions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sources_jurisdiction', 'monitored_sources', ['jurisdiction_id'], unique=False)
    op.create_index('idx_sources_status', 'monitored_sources', ['status'], unique=False)

    op.create_table('tax_rates',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('jurisdiction_id', sa.BigInteger(), nullable=False),
    sa.Column('tax_category_id', sa.BigInteger(), nullable=False),
    sa.Column('rate_type', sa.Text(), nullable=False),
    sa.Column('rate_value', sa.Numeric(precision=12, scale=6), nullable=True),
    sa.Column('currency_code', sa.Text(), nullable=True),
    sa.Column('tiers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('tier_type', sa.Text(), nullable=True),
    sa.Column('enacted_date', sa.Date(), nullable=True),
    sa.Column('effective_start', sa.Date(), nullable=False),
    sa.Column('effective_end', sa.Date(), nullable=True),
    sa.Column('applicability_start', sa.Date(), nullable=True),
    sa.Column('announcement_date', sa.Date(), nullable=True),
    sa.Column('calculation_order', sa.Integer(), nullable=False),
    sa.Column('base_includes', postgresql.ARRAY(sa.Text()), nullable=False),
    sa.Column('legal_reference', sa.Text(), nullable=True),
    sa.Column('legal_uri', sa.Text(), nullable=True),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('authority_name', sa.Text(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('supersedes_id', sa.BigInteger(), nullable=True),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=False),
    sa.Column('reviewed_by', sa.Text(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('review_notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['jurisdiction_id'], ['jurisdictions.id'], ),
    sa.ForeignKeyConstraint(['supersedes_id'], ['tax_rates.id'], ),
    sa.ForeignKeyConstraint(['tax_category_id'], ['tax_categories.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_tax_rates_jurisdiction', 'tax_rates', ['jurisdiction_id'], unique=False)
    op.create_index('idx_tax_rates_status', 'tax_rates', ['status'], unique=False)

    op.create_table('tax_rules',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('tax_rate_id', sa.BigInteger(), nullable=True),
    sa.Column('jurisdiction_id', sa.BigInteger(), nullable=False),
    sa.Column('rule_type', sa.Text(), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('action', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('effective_start', sa.Date(), nullable=False),
    sa.Column('effective_end', sa.Date(), nullable=True),
    sa.Column('enacted_date', sa.Date(), nullable=True),
    sa.Column('legal_reference', sa.Text(), nullable=True),
    sa.Column('legal_uri', sa.Text(), nullable=True),
    sa.Column('authority_name', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('supersedes_id', sa.BigInteger(), nullable=True),
    sa.Column('created_by', sa.Text(), nullable=False),
    sa.Column('reviewed_by', sa.Text(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['jurisdiction_id'], ['jurisdictions.id'], ),
    sa.ForeignKeyConstraint(['supersedes_id'], ['tax_rules.id'], ),
    sa.ForeignKeyConstraint(['tax_rate_id'], ['tax_rates.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_tax_rules_jurisdiction', 'tax_rules', ['jurisdiction_id'], unique=False)
    op.create_index('idx_tax_rules_rate', 'tax_rules', ['tax_rate_id'], unique=False)
    op.create_index('idx_tax_rules_status', 'tax_rules', ['status'], unique=False)
    op.create_index('idx_tax_rules_type', 'tax_rules', ['rule_type'], unique=False)

    op.create_table('detected_changes',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('source_id', sa.BigInteger(), nullable=True),
    sa.Column('jurisdiction_id', sa.BigInteger(), nullable=True),
    sa.Column('change_type', sa.Text(), nullable=False),
    sa.Column('detected_at', sa.DateTime(), nullable=False),
    sa.Column('extracted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('confidence', sa.Numeric(precision=3, scale=2), nullable=False),
    sa.Column('source_quote', sa.Text(), nullable=True),
    sa.Column('source_snapshot_url', sa.Text(), nullable=True),
    sa.Column('review_status', sa.Text(), nullable=False),
    sa.Column('reviewed_by', sa.Text(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('review_notes', sa.Text(), nullable=True),
    sa.Column('applied_rate_id', sa.BigInteger(), nullable=True),
    sa.Column('applied_rule_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['applied_rate_id'], ['tax_rates.id'], ),
    sa.ForeignKeyConstraint(['applied_rule_id'], ['tax_rules.id'], ),
    sa.ForeignKeyConstraint(['jurisdiction_id'], ['jurisdictions.id'], ),
    sa.ForeignKeyConstraint(['source_id'], ['monitored_sources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_changes_detected', 'detected_changes', ['detected_at'], unique=False)
    op.create_index('idx_changes_jurisdiction', 'detected_changes', ['jurisdiction_id'], unique=False)
    op.create_index('idx_changes_status', 'detected_changes', ['review_status'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_changes_status', table_name='detected_changes')
    op.drop_index('idx_changes_jurisdiction', table_name='detected_changes')
    op.drop_index('idx_changes_detected', table_name='detected_changes')
    op.drop_table('detected_changes')
    op.drop_index('idx_tax_rules_type', table_name='tax_rules')
    op.drop_index('idx_tax_rules_status', table_name='tax_rules')
    op.drop_index('idx_tax_rules_rate', table_name='tax_rules')
    op.drop_index('idx_tax_rules_jurisdiction', table_name='tax_rules')
    op.drop_table('tax_rules')
    op.drop_index('idx_tax_rates_status', table_name='tax_rates')
    op.drop_index('idx_tax_rates_jurisdiction', table_name='tax_rates')
    op.drop_table('tax_rates')
    op.drop_index('idx_sources_status', table_name='monitored_sources')
    op.drop_index('idx_sources_jurisdiction', table_name='monitored_sources')
    op.drop_table('monitored_sources')
    op.drop_table('tax_categories')
    op.drop_table('property_classifications')
    op.drop_index(op.f('ix_jurisdictions_parent_id'), table_name='jurisdictions')
    op.drop_index('idx_jurisdictions_type', table_name='jurisdictions')
    op.drop_index('idx_jurisdictions_country', table_name='jurisdictions')
    op.drop_table('jurisdictions')
    op.drop_index('idx_audit_time', table_name='audit_log')
    op.drop_index('idx_audit_source', table_name='audit_log')
    op.drop_index('idx_audit_entity', table_name='audit_log')
    op.drop_table('audit_log')
