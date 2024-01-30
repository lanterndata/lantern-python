import json
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from .models import Item
from lantern_django import L2Distance, TextEmbedding

@csrf_exempt
def index(request):

    results = Item.objects.annotate(distance=L2Distance('embedding', [3, 1, 2]))

    results_list = [{
        "title": result.id,
        "distance": result.distance
    } for result in results]

    return JsonResponse({"results": results_list})
