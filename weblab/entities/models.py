from pathlib import Path

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from git import Actor, Repo


class Entity(models.Model):
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_RESTRICTED = 'restricted'
    VISIBILITY_PUBLIC = 'public'

    VISIBILITY_CHOICES = (
        (VISIBILITY_PRIVATE, 'Private'),
        (VISIBILITY_RESTRICTED, 'Restricted'),
        (VISIBILITY_PUBLIC, 'Public')
    )
    VISIBILITY_HELP = (
        'Public = anyone can view\n'
        'Restricted = logged in users can view\n'
        'Private = only you can view'
    )

    ENTITY_TYPE_MODEL = 'model'
    ENTITY_TYPE_PROTOCOL = 'protocol'
    ENTITY_TYPE_CHOICES = (
        (ENTITY_TYPE_MODEL, ENTITY_TYPE_MODEL),
        (ENTITY_TYPE_PROTOCOL, ENTITY_TYPE_PROTOCOL),
    )

    entity_type = models.CharField(
        max_length=16,
        choices=ENTITY_TYPE_CHOICES,
    )

    name = models.CharField(validators=[MinLengthValidator(2)], max_length=255)
    creation_date = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL)
    visibility = models.CharField(
        max_length=16,
        choices=VISIBILITY_CHOICES,
        help_text=VISIBILITY_HELP.replace('\n', '<br />'),
    )

    class Meta:
        ordering = ['name']
        unique_together = ('entity_type', 'name', 'author')
        permissions = (
            ('create_model', 'Can create models'),
            ('create_protocol', 'Can create protocols'),
            ('create_model_version', 'Can create new versions of a model'),
            ('create_protocol_version', 'Can create new versions of a protocol'),
        )

    def __str__(self):
        return self.name

    def init_repo(self):
        """
        Create an empty repository
        """
        Repo.init(str(self.repo_abs_path))

    def add_file_to_repo(self, file_path):
        """
        Add a file to the repository

        :param file_path: Path of file to be added
        """
        self.repo.index.add([file_path])

    def commit_repo(self, message, author_name, author_email):
        """
        Commit changes to the repository

        :param message: Commit message
        :param author_name: Name of commit author (and also committer)
        :param author_email: Email of commit author (and also committer)

        :return: `git.Commit` object
        """
        return self.repo.index.commit(
            message,
            author=Actor(author_name, author_email),
            committer=Actor(author_name, author_email),
        )

    def tag_repo(self, tag, *, ref='HEAD'):
        """
        Tag the repository at the latest (or a given) commit, using the given tag

        :param tag: Tag name to use
        :param ref: A reference to a specific commit, defaults to the latest
        """
        self.repo.create_tag(tag, ref=ref)

    @property
    def repo(self):
        """
        Get a repository object for this entity

        :return: `git.Repo` object
        """
        return Repo(str(self.repo_abs_path))

    @property
    def repo_abs_path(self):
        """
        Absolute filesystem path for this entity's repository

        :return: `Path` object
        """
        return Path(settings.REPO_BASE, self.repo_rel_path)

    @property
    def repo_rel_path(self):
        """
        Filesystem path for this entity's repository relative to repo base dir


        :return: `Path` object
        """
        return Path('%d/%ss/%d' % (self.author.id, self.entity_type, self.id))

    @property
    def tag_dict(self):
        """
        Mapping of commits to git tags in the entity repository

        :return: dict of the form { `git.Commit`: ['tag_name'] }
        """
        tags = {}
        for tag in self.repo.tags:
            tags.setdefault(tag.commit, []).append(tag)
        return tags

    @property
    def commits(self):
        """
        :return iterable of `git.Commit` objects in the entity repository
        """
        return self.repo.iter_commits()


class EntityManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(entity_type=self.model.entity_type)

    def create(self, **kwargs):
        kwargs['entity_type'] = self.model.entity_type
        return super().create(**kwargs)


class ModelEntity(Entity):
    entity_type = Entity.ENTITY_TYPE_MODEL

    objects = EntityManager()

    class Meta:
        proxy = True
        verbose_name_plural = 'Model entities'


class ProtocolEntity(Entity):
    entity_type = Entity.ENTITY_TYPE_PROTOCOL

    objects = EntityManager()

    class Meta:
        proxy = True
        verbose_name_plural = 'Protocol entities'


class EntityFile(models.Model):
    entity = models.ForeignKey(Entity, related_name='files')
    upload = models.FileField(upload_to='uploads')
    original_name = models.CharField(max_length=255)

    def __str__(self):
        return self.original_name
