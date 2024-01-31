
from django.core import serializers
import numpy as np
from lantern_django import L2Distance, CosineDistance, TextEmbedding
from unittest import mock
from django.test import TestCase
from ..models import Item

def create_items():
    vectors = [
        [1, 1, 1],
        [2, 2, 2],
        [1, 1, 2]
    ]
    for i, v in enumerate(vectors):
        item = Item(id=i + 1, embedding=v + [0] * 381, title='test', country='US', state='CA', city='San Francisco', company_name='Google')
        item.save()

class TestDjangoLantern(TestCase):
    def setUp(self):
        Item.objects.all().delete()

    def test_works(self):
        item = Item(id=1, embedding=[1, 2, 3] + [0] * 381, title='test', country='US', state='CA', city='San Francisco', company_name='Google')
        item.save()
        item = Item.objects.get(pk=1)
        self.assertEqual(item.id, 1)
        self.assertTrue(np.array_equal(np.array(item.embedding), np.array([1, 2, 3] + [0] * 381)))

    def test_l2sq_distance(self):
        create_items()
        distance = L2Distance('embedding', [1, 1, 1] + [0] * 381)
        items = Item.objects.annotate(distance=distance).order_by(distance)
        self.assertEqual([v.id for v in items], [1, 3, 2])
        self.assertEqual([v.distance for v in items], [0, 1, 3])

    def test_cosine_distance(self):
        create_items()
        distance = CosineDistance('embedding', [1, 1, 1] + [0] * 381)
        items = Item.objects.annotate(distance=distance).order_by(distance)
        self.assertEqual([v.id for v in items], [1, 2, 3])
        # self.assertEqual([v.distance for v in items], [0, 0, 0.05719095841793653])

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
        item = Item(id=1, embedding=[1, 2, 3] + [0] * 381, title='test', country='US', state='CA', city='San Francisco', company_name='Google')
        item.full_clean()

    def test_get_or_create(self):
        Item.objects.get_or_create(embedding=[1, 2, 3] + [0] * 381, title='test', country='US', state='CA', city='San Francisco', company_name='Google')

    def test_missing(self):
        Item(title='test', country='US', state='CA', city='San Francisco', company_name='Google').save()
        assert Item.objects.first().embedding is None

