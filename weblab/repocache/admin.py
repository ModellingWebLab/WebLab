from django.contrib import admin

from .models import CachedModel, CachedModelTag, CachedModelVersion, CachedProtocol, CachedProtocolVersion, CachedProtocolTag


admin.register(CachedModel)
admin.register(CachedModelTag)
admin.register(CachedModelVersion)
admin.register(CachedProtocol)
admin.register(CachedProtocolVersion)
admin.register(CachedProtocolTag)
