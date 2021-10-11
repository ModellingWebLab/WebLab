from django.db import models
from django.db.models import TextField
from core.visibility import Visibility
from core.models import UserCreatedModelMixin, VisibilityModelMixin

from repocache.models import CachedModelVersion, CachedProtocolVersion
from entities.models import ModelGroup
#from markdownx.models import MarkdownxField


class Story(UserCreatedModelMixin, VisibilityModelMixin):
    """
    A story explaining how models and groups of model relate to each other.
    """
    DEFAULT_VISIBILITY = Visibility.PRIVATE

    permission_str = 'edit_story'
    title = models.CharField(max_length=255)

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
    story = models.ForeignKey(Story, null=False, blank=False, on_delete=models.CASCADE, related_name="storyparts")
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
