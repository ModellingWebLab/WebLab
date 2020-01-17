from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.text import get_valid_filename

from core.models import FileCollectionMixin, UserCreatedModelMixin, VisibilityModelMixin
from entities.models import ProtocolEntity


class Dataset(UserCreatedModelMixin, VisibilityModelMixin, FileCollectionMixin, models.Model):
    """Prototyping class for experimental datasets
    """
    name = models.CharField(validators=[MinLengthValidator(2)], max_length=255)

    description = models.TextField(validators=[MinLengthValidator(2)])

    protocol = models.ForeignKey(ProtocolEntity, related_name='protocol_experimental_datasets')

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
    dataset = models.ForeignKey(Dataset, related_name='file_uploads')
    upload = models.FileField(upload_to='uploads')
    original_name = models.CharField(max_length=255)

    def __str__(self):
        return self.original_name
