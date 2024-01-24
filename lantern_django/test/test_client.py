import os
import django
from django.conf import settings
from django.core import serializers
from django.db import connection, migrations, models
from django.contrib.postgres.fields import ArrayField
from django.db.migrations.loader import MigrationLoader
import numpy as np
from lantern_django import LanternExtension, LanternExtrasExtension, HnswIndex, L2Distance, CosineDistance, RealField, TextEmbedding
from unittest import mock

settings.configure(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'postgres'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
)
django.setup()


class Item(models.Model):
    embedding = ArrayField(RealField(), size=384, null=True)

    class Meta:
        app_label = 'myapp'
        indexes = [
            HnswIndex(
                name='hnsw_idx',
                fields=['embedding'],
                m=16,
                ef=64,
                ef_construction=64,
                dim=384,
                opclasses=['dist_l2sq_ops']
            )
        ]


class Migration(migrations.Migration):
    initial = True

    dependencies = [
    ]

    operations = [
        LanternExtension(),
        LanternExtrasExtension(),
        migrations.CreateModel(
            name='Item',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('embedding', ArrayField(RealField(), size=384, null=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='item',
            index=HnswIndex(
                fields=['embedding'],
                m=16,
                ef=64,
                ef_construction=64,
                dim=384,
                name='hnsw_idx',
                opclasses=['dist_l2sq_ops']
            ),
        )
    ]


migration = Migration('initial', 'myapp')
loader = MigrationLoader(connection, replace_migrations=False)
loader.graph.add_node(('myapp', migration.name), migration)
sql_statements = loader.collect_sql([(migration, False)])

with connection.cursor() as cursor:
    cursor.execute("DROP TABLE IF EXISTS myapp_item")
    cursor.execute('\n'.join(sql_statements))


def create_items():
    vectors = [
        [1, 1, 1],
        [2, 2, 2],
        [1, 1, 2]
    ]
    for i, v in enumerate(vectors):
        item = Item(id=i + 1, embedding=v + [0] * 381)
        item.save()


class TestDjango:
    def setup_method(self, test_method):
        Item.objects.all().delete()

    def test_works(self):
        item = Item(id=1, embedding=[1, 2, 3] + [0] * 381)
        item.save()
        item = Item.objects.get(pk=1)
        assert item.id == 1
        assert np.array_equal(np.array(item.embedding),
                              np.array([1, 2, 3] + [0] * 381))

    def test_l2sq_distance(self):
        create_items()
        distance = L2Distance('embedding', [1, 1, 1] + [0] * 381)
        items = Item.objects.annotate(distance=distance).order_by(distance)
        assert [v.id for v in items] == [1, 3, 2]
        assert [v.distance for v in items] == [0, 1, 3]

    def test_cosine_distance(self):
        create_items()
        distance = CosineDistance('embedding', [1, 1, 1] + [0] * 381)
        items = Item.objects.annotate(distance=distance).order_by(distance)
        assert [v.id for v in items] == [1, 2, 3]
        # assert [v.distance for v in items] == [0, 0, 0.05719095841793653]
        # TODO: Remove this and uncomment above when double precision supported
        assert [v.distance for v in items] == [0, 0, 0.057191014]

    def test_filter(self):
        create_items()
        distance = L2Distance('embedding', [1, 1, 1] + [0] * 381)
        items = Item.objects.alias(distance=distance).filter(distance__lt=1)
        assert [v.id for v in items] == [1]

    def test_text_embedding(self):
        create_items()
        distance = L2Distance('embedding', TextEmbedding(
            'BAAI/bge-small-en', 'hello'))
        results = Item.objects.annotate(distance=distance).order_by('distance')
        assert [v.id for v in results] == [1, 3, 2]
        assert [v.distance for v in results] == [93.583, 95.45514, 103.85868]

    def test_limit(self):
        create_items()
        distance = L2Distance('embedding', [0] * 384)
        results = Item.objects.annotate(
            distance=distance).order_by('distance')[:1]
        assert str(results.query).endswith("LIMIT 1")

    def test_serialization(self):
        create_items()
        items = Item.objects.all()
        for format in ['json', 'xml']:
            data = serializers.serialize(format, items)
            with mock.patch('django.core.serializers.python.apps.get_model') as get_model:
                get_model.return_value = Item
                for obj in serializers.deserialize(format, data):
                    obj.save()

    def test_clean(self):
        item = Item(id=1, embedding=[1, 2, 3] + [0] * 381)
        item.full_clean()

    def test_get_or_create(self):
        Item.objects.get_or_create(embedding=[1, 2, 3] + [0] * 381)

    def test_missing(self):
        Item().save()
        assert Item.objects.first().embedding is None
