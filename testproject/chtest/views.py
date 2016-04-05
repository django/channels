from django.http import HttpResponse
from django.shortcuts import render_to_response


def plain_text(request):
    return HttpResponse("OK")


def websocket_test(request):

    return render_to_response("chtest/base.html")


def group_test(request):

    return render_to_response("chtest/group.html")
