from django.contrib import admin
from markdownx.admin import MarkdownxModelAdmin
from markdownx.widgets import AdminMarkdownxWidget

from .models import EntityFile, ModelEntity, ProtocolEntity, ModelGroup#, Story


admin.site.register(EntityFile)
admin.site.register(ModelEntity)
admin.site.register(ProtocolEntity)
admin.site.register(ModelGroup)
#admin.site.register(Story, MarkdownxModelAdmin)
