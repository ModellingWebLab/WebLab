from django.contrib import admin

from .models import CachedEntity, CachedEntityTag, CachedEntityVersion


admin.register(CachedEntity)
admin.register(CachedEntityTag)
admin.register(CachedEntityVersion)
