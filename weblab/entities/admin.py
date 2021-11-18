from django.contrib import admin

from .models import EntityFile, ModelEntity, ProtocolEntity, ModelGroup


admin.site.register(EntityFile)
admin.site.register(ModelEntity)
admin.site.register(ProtocolEntity)
admin.site.register(ModelGroup)
