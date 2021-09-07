from django.db import models
from django.db.models import TextField
from core.visibility import Visibility
from core.models import UserCreatedModelMixin, VisibilityModelMixin

from entities.models import ModelEntity, ModelGroup
from experiments.models import Experiment
#from markdownx.models import MarkdownxField


class Story(UserCreatedModelMixin, VisibilityModelMixin):
    """
    A story explaining how models and groups of model relate to each other.
    """
    DEFAULT_VISIBILITY = Visibility.PRIVATE

    permission_str = 'edit_story'
    title = models.CharField(max_length=255)
    description = TextField()
    modelgroups = models.ManyToManyField(ModelGroup)
    othermodels = models.ManyToManyField(ModelEntity)
    experiments =  models.ManyToManyField(Experiment)

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


#class StoryText(models.Model):
#    text = TextField()
#    recipe = models.ForeignKey(Story, null=False, blank=False, on_delete=models.CASCADE, related_name="storytexts")
#
#    def __str__(self):
#        return self.text
