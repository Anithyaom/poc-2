from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from src.job.models import JobStatus
from uuid import uuid4
from tortoise import fields

class Migration(migrations.Migration):
    initial = True

    operations = [
        ops.CreateModel(
            name='GenerationJob',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('job_type', fields.CharField(max_length=64)),
                ('status', fields.CharField(default=JobStatus.QUEUED, max_length=32)),
                ('lab_id', fields.UUIDField(null=True)),
                ('target_id', fields.UUIDField(null=True)),
                ('artifact_id', fields.UUIDField(null=True)),
                ('celery_task_id', fields.CharField(null=True, max_length=255)),
                ('error', fields.TextField(null=True, unique=False)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={'table': 'generation_jobs', 'app': 'models', 'pk_attr': 'id', 'table_description': 'Domain-level status of a background generation.'},
            bases=['Model'],
        ),
        ops.CreateModel(
            name='SpikeSimulation',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('prompt', fields.TextField(unique=False)),
                ('manifest_json', fields.JSONField(encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('core_html', fields.TextField(unique=False)),
                ('raw_llm_response', fields.JSONField(null=True, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={'table': 'spike_simulations', 'app': 'models', 'pk_attr': 'id', 'table_description': 'Milestone-0 only.'},
            bases=['Model'],
        ),
    ]
