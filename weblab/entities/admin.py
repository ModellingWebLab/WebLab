from django.contrib import admin

from .models import EntityUpload, ModelEntity, ProtocolEntity


admin.site.register(EntityUpload)
admin.site.register(ModelEntity)
admin.site.register(ProtocolEntity)
