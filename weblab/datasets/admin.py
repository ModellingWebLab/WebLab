from django.contrib import admin

from .models import Dataset, DatasetFile


admin.site.register(Dataset)
admin.site.register(DatasetFile)
