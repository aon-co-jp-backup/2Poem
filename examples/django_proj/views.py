from django.http import JsonResponse
from django.shortcuts import render
from django.views import View


def year_archive(request, year):
    return JsonResponse({"year": year})


def legacy(request, pk):
    return JsonResponse({"pk": pk})


class Hello(View):
    def get(self, request):
        return JsonResponse({"hello": "world"})

    def post(self, request):
        return JsonResponse({"ok": True})


def home(request, name):
    return render(request, "home.html", {"name": name})
