from django.contrib import admin

from .models import Story, StoryGraph, StoryText


admin.site.register(Story)
admin.site.register(StoryText)
admin.site.register(StoryGraph)
