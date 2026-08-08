from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from tortoise.fields.base import OnDelete
from uuid import uuid4
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0004_backfill_time_stepped')]

    initial = False

    operations = [
        ops.CreateModel(
            name='Simulation',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('lab', fields.ForeignKeyField('models.Lab', source_field='lab_id', db_constraint=True, to_field='id', related_name='simulations', on_delete=OnDelete.CASCADE)),
                ('component_ref', fields.CharField(default='main', max_length=64)),
                ('version', fields.IntField()),
                ('manifest_json', fields.JSONField(encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('core_html', fields.TextField(unique=False)),
                ('raw_llm_response', fields.JSONField(null=True, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('is_current', fields.BooleanField(default=True)),
                ('change_summary', fields.TextField(null=True, unique=False)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={'table': 'simulations', 'app': 'models', 'unique_together': (('lab_id', 'component_ref', 'version'),), 'pk_attr': 'id', 'table_description': 'One generated simulation. Append-only, like every artifact here.'},
            bases=['Model'],
        ),
        # Hand-added: "exactly one current version" is a partial unique index, which
        # Tortoise's `unique_together` cannot express — it would forbid a second
        # *historical* row too. Without this the invariant lives only in task code,
        # and a crash between "insert v2" and "clear v1" leaves two current rows and
        # a workspace that renders whichever one Postgres returns first.
        ops.RunSQL(
            """
            CREATE UNIQUE INDEX uniq_simulations_current
                ON simulations (lab_id, component_ref)
             WHERE is_current;
            """,
            reverse_sql="DROP INDEX IF EXISTS uniq_simulations_current;",
        ),
    ]
