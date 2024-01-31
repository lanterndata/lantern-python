import json
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from .models import Item
from lantern_django import L2Distance, TextEmbedding

@csrf_exempt
def index(request):

    distance = L2Distance('embedding', TextEmbedding(
        'BAAI/bge-small-en', 'hello'))

    return JsonResponse({"results": distance})
