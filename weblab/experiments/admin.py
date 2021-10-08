from django.contrib import admin

from .models import Experiment, ExperimentVersion, RunningExperiment, PlannedExperiment


admin.site.register(ExperimentVersion)
admin.site.register(RunningExperiment)
admin.site.register(PlannedExperiment)


class ExperimentVersionInline(admin.StackedInline):
    model = ExperimentVersion
    extra = 0


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    inlines = [ExperimentVersionInline]
