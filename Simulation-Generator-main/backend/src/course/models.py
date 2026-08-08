from tortoise import fields
from tortoise.models import Model


class Course(Model):
    """A folder of labs — "Grade 9 Physics"."""

    id = fields.UUIDField(primary_key=True)
    title = fields.CharField(max_length=255)
    subject = fields.CharField(max_length=128)
    # The stub dev user's subject claim; the seam real auth drops into later.
    owner_sub = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)

    labs: fields.ReverseRelation["Lab"]  # noqa: F821

    class Meta:
        table = "courses"

    def __str__(self) -> str:
        return self.title
