"""Backfill `time_stepped` into blueprints written before the field existed.

`Plan` requires the field, and `plan_json` rows predating the transport bar do not
have it — so an old blueprint would 422 on accept-with-modifications and fail
manifest projection at milestone 3. These rows were authored when nothing could
step, so `false` is the truthful value, not merely the safe one. A teacher can
tick the box on any still-pending blueprint.

Data-only: the column is jsonb and its type does not change.
"""

from tortoise import migrations
from tortoise.migrations import operations as ops

class Migration(migrations.Migration):
    dependencies = [('models', '0003_auto_20260730_1929')]

    initial = False

    operations = [
        ops.RunSQL(
            """
            UPDATE plan_versions
               SET plan_json = jsonb_set(plan_json, '{time_stepped}', 'false'::jsonb, true)
             WHERE NOT (plan_json ? 'time_stepped');
            """,
            reverse_sql="""
            UPDATE plan_versions
               SET plan_json = plan_json - 'time_stepped';
            """,
        ),
    ]
