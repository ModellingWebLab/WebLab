from django.db import models
from django.db.models import BooleanField, ManyToManyField, TextField

from core.models import UserCreatedModelMixin, VisibilityModelMixin
from core.visibility import Visibility
from entities.models import ModelEntity, ModelGroup
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

    email_sent = models.BooleanField(default=False)  # Was alert that the story is affected by version caanges sent?

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
    cachedmodelversions = ManyToManyField(CachedModelVersion, blank=True,
                                          related_name='selected_group_story_modelversions')
    modelgroups = ManyToManyField(ModelGroup, blank=True, related_name='selected_group_story_graphs')
    models = ManyToManyField(ModelEntity, blank=True, related_name='selected_group_story_models')
    grouptoggles = ManyToManyField(ModelGroup, blank=True, related_name='toggle_group_story_graphs')
    protocol_is_latest = BooleanField(default=True)
    all_model_versions_latest = BooleanField(default=True)
    email_sent = BooleanField(default=False)
