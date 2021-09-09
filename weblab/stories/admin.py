from django.contrib import admin

from .models import Story, SimpleStory


admin.site.register(Story)
admin.site.register(SimpleStory)


#class StoryTextInline(admin.TabularInline):
#    model = StoryText
#    extra = 0
#
#@admin.register(Story)
#class StoryeAdmin(admin.ModelAdmin):
#    inlines = [StoryTextInline, ]
