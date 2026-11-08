from enum import StrEnum

from tortoise import fields
from tortoise.models import Model


class LabStatus(StrEnum):
    DRAFT = "draft"
    PLAN_REVIEW = "plan_review"
    PLAN_ACCEPTED = "plan_accepted"
    SIM_READY = "sim_ready"
    REFINING = "refining"


class Lab(Model):
    """One authored artifact: a description, a plan, and the sims generated from it.

    No `title` column — the human-readable title comes from `plan_json.title` once a
    plan exists, and before that the UI truncates `description`. One less thing to
    keep in sync.
    """

    id = fields.UUIDField(primary_key=True)
    course = fields.ForeignKeyField("models.Course", related_name="labs", on_delete=fields.CASCADE)
    description = fields.TextField()
    audience = fields.CharField(max_length=64)
    status = fields.CharField(max_length=32, default=LabStatus.DRAFT)
    # Set when a plan is accepted. Not a FK: plan_versions points at labs, and a
    # circular FK would make the migration ordering unnecessarily awkward.
    active_plan_id = fields.UUIDField(null=True)
    # Optional textbook section the blueprint is grounded in, e.g. "gp8:p2:c2:s4".
    # A ref into the mounted textbook JSON (src/textbook/library.py), not a FK: the
    # book is a read-only file, not a table.
    source_ref = fields.CharField(max_length=64, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "labs"
