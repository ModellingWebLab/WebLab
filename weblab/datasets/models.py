from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.text import get_valid_filename
from guardian.shortcuts import get_objects_for_user

from core.models import FileCollectionMixin, UserCreatedModelMixin, VisibilityModelMixin
from entities.models import ProtocolEntity
from repocache.models import CachedProtocolVersion, ProtocolIoputs


class DatasetQuerySet(models.QuerySet):
    def visible_to_user(self, user):
        """Query over all datasets that the given user can view.
        """
        non_private = self.filter(visibility__in=['public', 'moderated'])
        mine = self.filter(author=user) if user.is_authenticated else self.none()
        shared = self.shared_with_user(user)
        return non_private | mine | shared

    def shared_with_user(self, user):
        """Query over all datasets shared explicitly with the given user."""
        if user.is_authenticated:
            shared_pks = get_objects_for_user(
                user, 'entities.edit_entity', with_superuser=False).values_list('pk', flat=True)
            return self.filter(pk__in=shared_pks)
        else:
            return self.none()


class Dataset(UserCreatedModelMixin, VisibilityModelMixin, FileCollectionMixin, models.Model):
    """Prototyping class for experimental datasets
    """
    name = models.CharField(validators=[MinLengthValidator(2)], max_length=255)

    description = models.TextField(validators=[MinLengthValidator(2)])

    protocol = models.ForeignKey(ProtocolEntity, related_name='protocol_experimental_datasets',
                                 on_delete=models.CASCADE)

    objects = DatasetQuerySet.as_manager()

    class Meta:
        ordering = ['name']
        unique_together = ('name', 'author')
        verbose_name_plural = 'Datasets'

        permissions = (
            ('create_dataset', 'Can create experimental datasets'),
        )

    def __str__(self):
        return self.name

    @property
    def abs_path(self):
        return self.author.get_storage_dir('dataset') / str(self.id)

    @property
    def archive_name(self):
        return get_valid_filename(self.name + '.zip')


class DatasetFile(models.Model):
    dataset = models.ForeignKey(Dataset, related_name='file_uploads', on_delete=models.CASCADE)
    upload = models.FileField(upload_to='uploads')
    original_name = models.CharField(max_length=255)

    def __str__(self):
        return self.original_name


class DatasetColumnMapping(models.Model):
    """
    Maps dataset columns to protocol inputs/outputs
    """
    dataset = models.ForeignKey(Dataset, related_name='column_mappings', on_delete=models.CASCADE)

    column_name = models.CharField(
        max_length=200,
        help_text='name of the column')

    column_units = models.CharField(
        blank=True,
        max_length=200,
        help_text='units of the column, as a pint definition string')

    protocol_version = models.ForeignKey(
        CachedProtocolVersion,
        help_text='Protocol version to link to',
        on_delete=models.CASCADE,
    )

    protocol_ioput = models.ForeignKey(
        ProtocolIoputs,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text='Protocol input or output to link to')

    class Meta:
        unique_together = ['dataset', 'column_name', 'protocol_version']
