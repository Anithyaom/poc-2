from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0002_auto_20260729_2117')]

    initial = False

    operations = [
        ops.AddField(
            model_name='PlanVersion',
            name='revision_feedback',
            field=fields.TextField(null=True, unique=False),
        ),
    ]
