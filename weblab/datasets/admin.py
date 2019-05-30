from django.contrib import admin

from .models import ExperimentalDataset, DatasetFile


admin.site.register(ExperimentalDataset)
admin.site.register(DatasetFile)