from django.contrib import admin

from .models import Story#, StoryText


admin.site.register(Story)

#class StoryTextInline(admin.TabularInline):
#    model = StoryText
#    extra = 0
#
#@admin.register(Story)
#class StoryeAdmin(admin.ModelAdmin):
#    inlines = [StoryTextInline, ]
