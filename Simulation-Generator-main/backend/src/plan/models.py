from enum import StrEnum

from tortoise import fields
from tortoise.models import Model


class PlanDecision(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    # The teacher edited this plan before accepting; a new row holds what they
    # accepted. Nothing is overwritten.
    SUPERSEDED = "superseded"


class PlanVersion(Model):
    """One generated (or teacher-edited) plan. Append-only.

    A rejection, a regeneration, and an edit-then-accept each produce a NEW row.
    `raw_llm_response` is null on rows a human authored by editing.
    """

    id = fields.UUIDField(primary_key=True)
    lab = fields.ForeignKeyField(
        "models.Lab", related_name="plan_versions", on_delete=fields.CASCADE
    )
    version = fields.IntField()
    raw_llm_response = fields.JSONField(null=True)
    plan_json = fields.JSONField()
    # The teacher's words that produced this row, when it came from a revision.
    # Without it the history shows *that* v4 replaced v3 but never *why* — which
    # is the first thing you want when a revision goes wrong.
    revision_feedback = fields.TextField(null=True)
    decision = fields.CharField(max_length=32, default=PlanDecision.PENDING)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "plan_versions"
        unique_together = (("lab_id", "version"),)
        ordering = ["version"]
