from tortoise import fields
from tortoise.models import Model

# The POC generates one simulation per lab. `component_ref` exists because the
# spec's data model allows a lab to hold several named components later; it is
# the constant "main" throughout the POC and is never shown to a teacher.
MAIN_COMPONENT = "main"


class Simulation(Model):
    """One generated simulation. Append-only, like every artifact here.

    A regeneration, an edit from feedback, and a rollback each produce or re-point
    to a row — never an update in place. Exactly one row per
    `(lab_id, component_ref)` carries `is_current`, which is what the workspace
    reads; the others are history.

    `manifest_json` is stored alongside `core_html` rather than re-projected from
    the plan on read. The plan can be revised after a simulation is generated, and
    the shell must keep rendering the controls this core was actually built
    against.
    """

    id = fields.UUIDField(primary_key=True)
    lab = fields.ForeignKeyField("models.Lab", related_name="simulations", on_delete=fields.CASCADE)
    component_ref = fields.CharField(max_length=64, default=MAIN_COMPONENT)
    version = fields.IntField()
    manifest_json = fields.JSONField()
    core_html = fields.TextField()
    # Kept for debugging: what the model actually returned, before validation.
    raw_llm_response = fields.JSONField(null=True)
    is_current = fields.BooleanField(default=True)
    # Written by the refinement loop (milestone 4): what changed and why. Null on
    # a v1, which needs no explanation beyond the blueprint it came from.
    change_summary = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "simulations"
        unique_together = (("lab_id", "component_ref", "version"),)
        ordering = ["version"]
