from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0006_auto_20260801_2338')]

    initial = False

    operations = [
        ops.AddField(
            model_name='Lab',
            name='source_ref',
            field=fields.CharField(null=True, max_length=64),
        ),
    ]
