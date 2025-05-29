from django.contrib import admin

from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("title", "created")
    change_list_template = "admin/sampleapp/message/change_list.html"
