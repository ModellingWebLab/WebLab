from django.db import models
from django.db.models import TextField
from django.db.utils import IntegrityError
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from core.visibility import Visibility
from core.models import UserCreatedModelMixin, VisibilityModelMixin

from repocache.models import CachedModelVersion, CachedProtocolVersion
from entities.models import ModelGroup


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
    graphfilename = TextField(blank=False)
    cachedprotocolversion = models.ForeignKey(CachedProtocolVersion, null=False, blank=False, on_delete=models.CASCADE,
                                              related_name="protocolforgraph")
    cachedmodelversions = models.ManyToManyField(CachedModelVersion)
    modelgroup = models.ForeignKey(ModelGroup, blank=True, null=True, default=None, on_delete=models.SET_DEFAULT)

    def __str__(self):
        return (self.modelgroup.title if self.modelgroup is not None
                else self.cachedmodelversions.first().model.name) +\
            " / " + self.cachedprotocolversion.protocol.name + " / " + self.graphfilename


@receiver(m2m_changed, sender=StoryGraph.cachedmodelversions.through)
def cachedmodelversions__changed(sender, **kwargs):
    action = kwargs.pop('action', '')
    instance = kwargs.pop('instance', None)
    if action.startswith('post'):
        if instance.cachedmodelversions.count() == 0:
            raise IntegrityError("StoryGraph must have model")
        if instance.modelgroup is None and instance.cachedmodelversions.count() != 1:
            raise IntegrityError("StoryGraph without modelgroup must have 1 model")
        if instance.modelgroup is not None:
            models_in_group = sorted(instance.modelgroup.models.all(), key=str)
            models_in_graph = sorted([m.model for m in instance.cachedmodelversions.all()], key=str)
            if models_in_group != models_in_graph:
                raise IntegrityError("Models in modelgroup and the cachedmodelversions don't match")
