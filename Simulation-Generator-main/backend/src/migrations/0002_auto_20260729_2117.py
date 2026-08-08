from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from src.lab.models import LabStatus
from src.plan.models import PlanDecision
from tortoise.fields.base import OnDelete
from uuid import uuid4
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0001_initial')]

    initial = False

    operations = [
        ops.CreateModel(
            name='Course',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('title', fields.CharField(max_length=255)),
                ('subject', fields.CharField(max_length=128)),
                ('owner_sub', fields.CharField(max_length=255)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={'table': 'courses', 'app': 'models', 'pk_attr': 'id', 'table_description': 'A folder of labs — "Grade 9 Physics".'},
            bases=['Model'],
        ),
        ops.CreateModel(
            name='Lab',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('course', fields.ForeignKeyField('models.Course', source_field='course_id', db_constraint=True, to_field='id', related_name='labs', on_delete=OnDelete.CASCADE)),
                ('description', fields.TextField(unique=False)),
                ('audience', fields.CharField(max_length=64)),
                ('status', fields.CharField(default=LabStatus.DRAFT, max_length=32)),
                ('active_plan_id', fields.UUIDField(null=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={'table': 'labs', 'app': 'models', 'pk_attr': 'id', 'table_description': 'One authored artifact: a description, a plan, and the sims generated from it.'},
            bases=['Model'],
        ),
        ops.CreateModel(
            name='PlanVersion',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('lab', fields.ForeignKeyField('models.Lab', source_field='lab_id', db_constraint=True, to_field='id', related_name='plan_versions', on_delete=OnDelete.CASCADE)),
                ('version', fields.IntField()),
                ('raw_llm_response', fields.JSONField(null=True, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('plan_json', fields.JSONField(encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('decision', fields.CharField(default=PlanDecision.PENDING, max_length=32)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={'table': 'plan_versions', 'app': 'models', 'unique_together': (('lab_id', 'version'),), 'pk_attr': 'id', 'table_description': 'One generated (or teacher-edited) plan. Append-only.'},
            bases=['Model'],
        ),
    ]
