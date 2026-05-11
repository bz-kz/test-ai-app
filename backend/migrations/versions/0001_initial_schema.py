"""Initial schema: patient, encounter, record_draft, record_final, audit_log.

Revision ID: 0001
Revises:
Create Date: 2026-05-11

PHI columns (phi=True in ORM info):
  patient      : mrn, family_name, given_name, date_of_birth
  record_draft : content
  record_final : content

Reviewer note: all five tables are created in this revision.
record_final is immutable by application convention (no UPDATE path).
audit_log is append-only by application convention (no UPDATE path).
No PHI test data is included in this migration.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # patient テーブル (PHI: mrn, family_name, given_name, date_of_birth)
    # ------------------------------------------------------------------
    op.create_table(
        "patient",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mrn", sa.String(), nullable=False),  # PHI
        sa.Column("family_name", sa.String(), nullable=False),  # PHI
        sa.Column("given_name", sa.String(), nullable=False),  # PHI
        sa.Column("date_of_birth", sa.DateTime(), nullable=False),  # PHI
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_mrn", "patient", ["mrn"])

    # ------------------------------------------------------------------
    # encounter テーブル
    # ------------------------------------------------------------------
    op.create_table(
        "encounter",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encountered_at", sa.DateTime(), nullable=False),
        sa.Column("clinician_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_encounter_patient_id", "encounter", ["patient_id"])

    # ------------------------------------------------------------------
    # record_draft テーブル (PHI: content)
    # ------------------------------------------------------------------
    op.create_table(
        "record_draft",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),  # PHI
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounter.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_record_draft_encounter_id", "record_draft", ["encounter_id"])

    # ------------------------------------------------------------------
    # record_final テーブル (PHI: content)
    # immutable: no UPDATE; corrections are new rows with predecessor_id
    # ------------------------------------------------------------------
    op.create_table(
        "record_final",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),  # PHI
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("clinician_id", sa.Uuid(), nullable=False),
        sa.Column("predecessor_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounter.id"]),
        sa.ForeignKeyConstraint(["predecessor_id"], ["record_final.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_record_final_encounter_id", "record_final", ["encounter_id"])

    # ------------------------------------------------------------------
    # audit_log テーブル — append-only
    # ------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("actor", sa.Uuid(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "patient_create",
                "encounter_create",
                "record_draft_create",
                "record_draft_update",
                "record_final_create",
                "record_final_correct",
                name="audit_action",
            ),
            nullable=False,
        ),
        sa.Column("target_kind", sa.String(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("meta_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_at", "audit_log", ["at"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("record_final")
    op.drop_table("record_draft")
    op.drop_table("encounter")
    op.drop_table("patient")
    op.execute("DROP TYPE IF EXISTS audit_action")
