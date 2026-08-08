from tortoise import migrations
from tortoise.migrations import operations as ops

class Migration(migrations.Migration):
    dependencies = [('models', '0005_auto_20260801_2245')]

    initial = False

    operations = [
        ops.DeleteModel(name='SpikeSimulation'),
    ]
