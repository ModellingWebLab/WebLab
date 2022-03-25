from django.db import models
from django.db.models import TextField
from django.db.models.signals import m2m_changed
from django.db.utils import IntegrityError
from django.dispatch import receiver

from core.models import UserCreatedModelMixin, VisibilityModelMixin
from core.visibility import Visibility
from entities.models import ModelGroup
from repocache.models import CachedModelVersion, CachedProtocolVersion


class Story(UserCreatedModelMixin, VisibilityModelMixin):
    """
    A story explaining how models and groups of model relate to each other.
    """
    DEFAULT_VISIBILITY = Visibility.PRIVATE
    permission_str = 'edit_story'
    title = models.CharField(max_length=255)
    graphvisualizer = models.CharField(
        max_length=16,
        choices=(('displayPlotFlot', 'displayPlotFlot'),
                 ('displayPlotHC', 'displayPlotHC')),
        help_text='The different visualisers determine how graphs are shown in this story.',
        default='displayPlotFlot',
    )

    class Meta:
        ordering = ['title']
        unique_together = ['title', 'author']
        permissions = (
            # edit_story is used as an object-level permission for the collaborator functionality
            ('edit_story', 'Can edit story'),
        )

    def visible_to_user(self, user):
        return self.is_editable_by(user) or self.visibility != 'private'

    def is_editable_by(self, user):
        return (
            user == self.author or
            user.has_perm(self.permission_str, self)
        )

    def __str__(self):
        return self.title


class StoryItem(UserCreatedModelMixin):
    story = models.ForeignKey(Story, null=False, blank=False, on_delete=models.CASCADE, related_name="+")
    order = models.IntegerField()


class StoryText(StoryItem):
    """
    A textual (markdown) part of a story.
    """
    description = TextField(blank=True, default='')

    def __str__(self):
        return self.description


class StoryGraph(StoryItem):
    """
    A graph for a story
    """
    graphfilename = TextField(blank=True, null=True)
    cachedprotocolversion = models.ForeignKey(CachedProtocolVersion, null=False, blank=False, on_delete=models.CASCADE,
                                              related_name="protocolforgraph")
    cachedmodelversions = models.ManyToManyField(CachedModelVersion)
    modelgroup = models.ForeignKey(ModelGroup, blank=True, null=True, default=None, on_delete=models.SET_DEFAULT)

    def __str__(self):
        return (self.modelgroup.title if self.modelgroup is not None
                else self.cachedmodelversions.first().model.name) +\
            f' / {self.cachedprotocolversion.protocol.name} / {self.graphfilename}'

    def set_cachedmodelversions(self, cachedmodelversions):
        self.setting_cachedmodelversions = True
        self.save()
        self.cachedmodelversions.set(cachedmodelversions)
        self.setting_cachedmodelversions = False
        self.save()


@receiver(m2m_changed, sender=StoryGraph.cachedmodelversions.through)
def storygraph_constraints(sender, **kwargs):
    """
    enforce constriants for StoryGraph
    """
    action = kwargs.pop('action', '')
    instance = kwargs.pop('instance', None)
    if action.startswith('post') and not getattr(instance, 'setting_cachedmodelversions', False):
        # must have at least 1 cachedmodelversion
        if instance.cachedmodelversions.count() == 0:
            raise IntegrityError("StoryGraph must have model")
        # if using mdel group must have exactly 1 cachedmodelversion
        if instance.modelgroup is None and instance.cachedmodelversions.count() != 1:
            raise IntegrityError("StoryGraph without modelgroup must have 1 model")
        # models in modelgroup must be the same as the ones referenced in cachedmodelversions
        if instance.modelgroup is not None:
            models_in_group = sorted(instance.modelgroup.models.all(), key=str)
            models_in_graph = sorted([m.model for m in instance.cachedmodelversions.all()], key=str)
            if models_in_group != models_in_graph:
                raise IntegrityError("Models in modelgroup and the cachedmodelversions don't match")
