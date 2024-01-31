from django.contrib.postgres.operations import CreateExtension
from django.contrib.postgres.indexes import PostgresIndex
from django.db.models import FloatField, Func, Value
import numpy as np


__all__ = ['LanternExtension', 'LanternExtrasExtension',
           'L2Distance', 'CosineDistance', 'HnswIndex']


def to_db(value):
    if value is None:
        return value

    if isinstance(value, np.ndarray):
        if value.ndim != 1:
            raise ValueError('expected ndim to be 1')
        if not np.issubdtype(value.dtype, np.integer) and not np.issubdtype(value.dtype, np.floating):
            raise ValueError('dtype must be numeric')
        value = value.tolist()

    return value


# TODO: Remove this once we support double precision
class RealField(FloatField):
    description = "Single precision floating point number"

    def db_type(self, connection):
        if connection.settings_dict['ENGINE'] == 'django.db.backends.postgresql':
            return 'real'
        return super().db_type(connection)


class LanternExtension(CreateExtension):
    def __init__(self):
        self.name = 'lantern'


class LanternExtrasExtension(CreateExtension):
    def __init__(self):
        self.name = 'lantern_extras'


class HnswIndex(PostgresIndex):
    suffix = 'hnsw'

    def __init__(self, *expressions, m=None, ef=None, ef_construction=None, dim=None, **kwargs):
        self.m = m
        self.ef_construction = ef_construction
        self.ef = ef
        self.dim = dim
        super().__init__(*expressions, **kwargs)

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        if self.m is not None:
            kwargs['m'] = self.m
        if self.ef is not None:
            kwargs['ef'] = self.ef
        if self.ef_construction is not None:
            kwargs['ef_construction'] = self.ef_construction
        if self.dim is not None:
            kwargs['dim'] = self.dim
        return path, args, kwargs

    def get_with_params(self):
        with_params = []
        if self.m is not None:
            with_params.append('m = %d' % self.m)
        if self.ef is not None:
            with_params.append('ef = %d' % self.ef)
        if self.ef_construction is not None:
            with_params.append('ef_construction = %d' % self.ef_construction)
        if self.dim is not None:
            with_params.append('dim = %d' % self.dim)
        return with_params


class DistanceBase(Func):
    output_field = RealField()

    def __init__(self, expression, vector, **extra):
        if not hasattr(vector, 'resolve_expression'):
            vector = Value(to_db(vector))
        super().__init__(expression, vector, **extra)


class L2Distance(DistanceBase):
    function = ''
    arg_joiner = ' <-> '


class HammingDistance(DistanceBase):
    function = ''
    arg_joiner = ' <+> '


class CosineDistance(DistanceBase):
    function = ''
    arg_joiner = ' <=> '


class TextEmbedding(Func):
    function = 'text_embedding'

    def __init__(self, model, text, **extra):
        if not hasattr(text, 'resolve_expression'):
            text = Value(text)
        super().__init__(Value(model), text, **extra)


class ImageEmbedding(Func):
    function = 'image_embedding'

    def __init__(self, model, text, **extra):
        if not hasattr(text, 'resolve_expression'):
            text = Value(text)
        super().__init__(Value(model), text, **extra)
