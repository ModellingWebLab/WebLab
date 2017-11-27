from django.contrib import admin

from .models import EntityFile, ModelEntity, ProtocolEntity


admin.site.register(EntityFile)
admin.site.register(ModelEntity)
admin.site.register(ProtocolEntity)
