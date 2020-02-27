from django.contrib import admin

from .models import Experiment, ExperimentVersion


class ExperimentVersionInline(admin.StackedInline):
    model = ExperimentVersion
    extra = 0


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    inlines = [ExperimentVersionInline]
