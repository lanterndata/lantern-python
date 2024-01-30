# Create your models here.
from django.db import models
from django.contrib.postgres.fields import ArrayField
from lantern_django import HnswIndex, RealField

class Item(models.Model):
    embedding = ArrayField(RealField(), size=3, null=True)

    class Meta:
        indexes = [
            HnswIndex(
                name='hnsw_idx',
                fields=['embedding'],
                m=16,
                ef=64,
                ef_construction=64,
                dim=3,
                opclasses=['dist_l2sq_ops']
            )
        ]