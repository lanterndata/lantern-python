# Django Client for Lantern

## Install

```sh
pip install lantern-django
```

## Basic usage

Create a migration to enable the extensions:

```python
from django.db import migrations
from lantern_django import LanternExtension, LanternExtrasExtension

class Migration(migrations.Migration):
    operations = [
        LanternExtension(),
        LanternExtrasExtension(),
    ]
```

Add a `REAL[]` field to your model

```python
from django.db import models
from django.contrib.postgres.fields import ArrayField
from lantern_django import RealField

class Item(models.Model):
    embedding = ArrayField(RealField(), size=3, null=True)
```

Insert a vector

```python
item = Item(embedding=[1, 2, 3])
item.save()
```

Get the nearest neighbors to a vector

```python
from lantern_django import L2Distance

Item.objects.order_by(L2Distance('embedding', [3, 1, 2]))[:5]
```

Get nearest neighbors to a text embedding

```python
distance = L2Distance('embedding', TextEmbedding(
            'BAAI/bge-small-en', 'hello'))
        results = Item.objects.annotate(distance=distance).order_by('distance')[:5]
```

Get the distance

```python
Item.objects.annotate(distance=L2Distance('embedding', [3, 1, 2]))
```

Get items within a certain distance

```python
Item.objects.alias(distance=L2Distance('embedding', [3, 1, 2])).filter(distance__lt=5)
```

Add an index

```python
from lantern_django import HnswIndex

class Item(models.Model):
    class Meta:
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
```
