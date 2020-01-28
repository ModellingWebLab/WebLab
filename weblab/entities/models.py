import binascii
import uuid
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.core.validators import MinLengthValidator
from django.db import models
from guardian.shortcuts import get_objects_for_user

from core.filetypes import get_file_type
from core.models import UserCreatedModelMixin
from core.visibility import HELP_TEXT as VIS_HELP_TEXT
from core.visibility import Visibility, visibility_check
from repocache.exceptions import RepoCacheMiss

from .repository import Repository


VISIBILITY_NOTE_PREFIX = 'Visibility: '


class Entity(UserCreatedModelMixin, models.Model):
    """
    Base class for 'entities' - conceptual entities backed by git repositories.

    Subclasses describe (CellML) models, protocols, and fitting specifications.

    The entity_type column states which concrete type each DB row represents, and is fixed by each subclass.
    In addition, other class properties defined in subclasses refer to these types in helpful ways:
    - ``other_type`` refers to the other axis on a models vs protocols matrix
    - ``display_type`` is used to display the type of the entity to users in templates
    - ``url_type`` is used as a URL fragment to refer to this entity type
    """
    DEFAULT_VISIBILITY = Visibility.PRIVATE

    VISIBILITY_HELP = VIS_HELP_TEXT

    ENTITY_TYPE_MODEL = 'model'
    ENTITY_TYPE_PROTOCOL = 'protocol'
    ENTITY_TYPE_FITTINGSPEC = 'fittingspec'
    ENTITY_TYPE_CHOICES = (
        (ENTITY_TYPE_MODEL, ENTITY_TYPE_MODEL),
        (ENTITY_TYPE_PROTOCOL, ENTITY_TYPE_PROTOCOL),
        (ENTITY_TYPE_FITTINGSPEC, ENTITY_TYPE_FITTINGSPEC),
    )

    entity_type = models.CharField(
        max_length=16,
        choices=ENTITY_TYPE_CHOICES,
    )

    name = models.CharField(validators=[MinLengthValidator(2)], max_length=255)

    is_fitting_spec = models.BooleanField(
        default=False,
        help_text="This protocol is a parameter fitting specification",
    )

    class Meta:
        ordering = ['name']
        unique_together = ('entity_type', 'name', 'author')
        permissions = (
            ('create_model', 'Can create models'),
            ('create_protocol', 'Can create protocols'),
            ('create_fittingspec', 'Can create fitting specifications'),
            # Edit entity is used as an object-level permission
            ('edit_entity', 'Can edit entity'),
            ('moderator', 'Can promote public entity versions to moderated'),
        )

    def __str__(self):
        return self.name

    @property
    def repo(self):
        """This entity's git repository wrapper.

        Note that we do not cache this property as this can lead to too many open files.
        See also https://gitpython.readthedocs.io/en/stable/intro.html#leakage-of-system-resources
        """
        return Repository(self.repo_abs_path)

    @property
    def repo_abs_path(self):
        """
        Absolute filesystem path for this entity's repository

        :return: `Path` object
        """
        return Path(
            self.author.get_storage_dir('repo'), '%ss' % self.entity_type, str(self.id)
        )

    def nice_version(self, sha_or_tag):
        """
        Returns tag/sha with ellipses

        :param sha_or_tag: version sha or tag string
        :return version_name: string with the sha_or_tag formatted
        """
        version_name = self.repocache.get_name_for_version(sha_or_tag)
        if len(version_name) > 20:
            version_name = version_name[:8] + '...'
        return version_name

    def get_visibility_from_repo(self, commit):
        """
        Get the visibility of the given entity version from the repository

        :param commit: `repository.Commit` object
        :return visibility: string representing visibility
        """
        note = commit.get_note()
        if note and note.startswith(VISIBILITY_NOTE_PREFIX):
            return note[len(VISIBILITY_NOTE_PREFIX):]

    def set_visibility_in_repo(self, commit, visibility):
        """
        Set the visibility of the given entity version in the repository

        :param commit:`repository.Commit` object
        :param visibility: string representing visibility
        """
        commit.add_note('%s%s' % (VISIBILITY_NOTE_PREFIX, visibility))

    @property
    def repocache(self):
        from repocache.models import get_or_create_cached_entity
        return get_or_create_cached_entity(self)[0]

    @property
    def cachedentity(self):
        """Temporary workaround until ModelEntity and ProtocolEntity have their own tables."""
        name = 'cached' + self.entity_type
        return getattr(self, name)

    def set_version_visibility(self, commit, visibility):
        """
        Set the visibility of the given entity version

        Updates both the repository and the cache

        :param commit: ref of the relevant commit
        :param visibility: string representing visibility
        """
        commit = self.repo.get_commit(commit)
        self.set_visibility_in_repo(commit, visibility)

        self.repocache.get_version(commit.sha).set_visibility(visibility)

    def get_version_visibility(self, sha, default=None):
        """
        Get the visibility of the given entity version

        This is fetched from the repocache

        :param sha: SHA of the relevant commit
        :param default: Default visibility if no entry found - defaults to `None`

        :return: string representing visibility
        :raise: RepoCacheMiss if entry not found and no default set
        """
        try:
            return self.repocache.get_version(sha).visibility
        except RepoCacheMiss:
            if default is not None:
                return default
            else:
                raise

    @staticmethod
    def _is_valid_sha(ref):
        if len(ref) == 40:
            try:
                binascii.unhexlify(ref)
                return True
            except binascii.Error:
                return False

        return False

    def get_ref_version_visibility(self, ref):
        """
        Get the visibility of the given entity version, with ref lookup

        :param ref: ref of the relevant commit (SHA, tag or 'latest')
        """
        if ref == 'latest':
            return self.repocache.visibility

        if self._is_valid_sha(ref):
            return self.get_version_visibility(ref)

        try:
            return self.repocache.tags.get(tag=ref).version.visibility
        except ObjectDoesNotExist:
            raise RepoCacheMiss("Entity version not found")

    def add_tag(self, tagname, ref):
        """
        Add a tag for the given entity version

        Updates both the repository and the cache

        :param tagname: Name of tag
        :param ref: ref of the relevant commit
        """
        commit = self.repo.get_commit(ref)
        self.repo.tag(tagname, ref=ref)
        try:
            self.repocache.get_version(commit.sha).tag(tagname)
        except RepoCacheMiss:
            pass

    @property
    def visibility(self):
        """
        Get the visibility of an entity

        This is fetched from the repocache

        :return: string representing visibility,
            or 'private' if visibility not available
        """
        return self.repocache.visibility

    def get_tags(self, sha):
        """
        Get the tags for the given entity version

        This is fetched from the repocache.

        :param sha: SHA of the relevant commit
        :return: set of tag names for the commit
        """
        return set(self.repocache.get_version(sha).tags.values_list('tag', flat=True))

    def analyse_new_version(self, commit):
        """Hook called when a new version has been created successfully.

        This can be used by subclasses to, e.g., add ephemeral files to the commit,
        or trigger Celery tasks to analyse the new entity.

        Warning: this doesn't function like a normal polymorphic method for objects
        retrieved from the database. You'll get an instance of whatever class you
        request, so if you search for any Entity you'll end up calling this method,
        not the subclass implementation as you might have expected. If this turns
        out to be a problem in practice, we can look at using django-polymorphic as
        a solution.

        :param commit: a `Commit` object for the new version
        """
        pass

    def is_version_visible_to_user(self, hexsha, user):
        """
        Is a version of the entity visible to the user?

        :param hexsha: SHA of the relevant ccommit
        :param user: `User` object

        :return: True if visible to user, False otherwise
        """
        return visibility_check(
            self.get_version_visibility(hexsha),
            self.viewers,
            user
        )

    def is_parsed_ok(self, version):
        """Whether the files comprising this entity version are syntactically correct.

        Only protocols are checked at present, on upload, and the result cached in the DB.

        :param version: a `CachedProtocolVersion` instance or sha referencing a version
        """
        from repocache.models import CachedProtocolVersion
        if isinstance(version, CachedProtocolVersion):
            ok = version.parsed_ok
        else:
            ok = self.repocache.get_version(version).parsed_ok
        return ok

    def get_version_json(self, commit, ns):
        """Get metadata for a particular version of this entity suitable for sending as JSON.

        :param commit: a `Commit` instance (TODO #191 a `CachedEntityVersion` instance)
        :param str ns: the app namespace to use for reversing download URLs
        :return: a dictionary of version metadata, including file info
        """
        files = [
            self.get_file_json(commit, f, ns)
            for f in commit.files
            if f.name not in ['manifest.xml', 'metadata.rdf']
        ]
        return {
            'id': commit.sha,
            'entityId': self.id,
            'author': commit.author.name,
            'parsedOk': self.is_parsed_ok(commit.sha),
            'visibility': self.get_version_visibility(commit.sha, default=self.DEFAULT_VISIBILITY),
            'created': commit.timestamp,
            'name': self.name,
            'version': self.repocache.get_name_for_version(commit.sha),
            'files': files,
            'commitMessage': commit.message,
            'numFiles': len(files),
            'url': reverse(
                ns + ':version',
                args=[self.url_type, self.id, commit.sha]
            ),
        }

    def get_file_json(self, commit, file_, ns):
        """Get metadata for a single file within a commit suitable for sending as JSON.

        TODO #191 consider how to replace Commit with CachedEntityVersion here. We'd need
        to cache the list of file names and sizes.

        :param commit: a `Commit` instance
        :param git.Blob file_: the file to get metadata for
        :param str ns: the app namespace to use for reversing download URLs
        :return: a dictionary of file metadata
        """
        return {
            'id': file_.name,
            'name': file_.name,
            'author': commit.author.name,
            'created': commit.timestamp,
            'filetype': get_file_type(file_.name),
            'size': file_.size,
            'url': reverse(
                ns + ':file_download',
                args=[self.url_type, self.id, commit.sha, file_.name]
            ),
        }


class EntityManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(entity_type=self.model.entity_type)

    def create(self, **kwargs):
        kwargs['entity_type'] = self.model.entity_type
        return super().create(**kwargs)

    def visible_to_user(self, user):
        """Query over all managed entities that the given user can view.

        This includes those entities of the managed ``entity_type`` for which either:
        - the user is the author
        - the entity has at least one non-private version
        - or the entity is explicitly shared with the user
        """
        from repocache.models import CACHED_VERSION_TYPE_MAP
        CachedEntityVersion = CACHED_VERSION_TYPE_MAP[self.model.entity_type]
        non_private = self.annotate(
            non_private=models.Exists(
                CachedEntityVersion.objects.filter(
                    entity__entity=models.OuterRef('pk'),
                    visibility__in=['public', 'moderated'],
                )
            )
        ).filter(
            non_private=True,
        )
        owned = self.filter(author=user)
        shared = self.shared_with_user(user)
        return owned | non_private | shared

    def shared_with_user(self, user):
        """Query over all managed entities shared explicitly with the given user."""
        if user.is_authenticated:
            shared_pks = get_objects_for_user(
                user, 'entities.edit_entity', with_superuser=False).values_list('pk', flat=True)
            return self.get_queryset().filter(pk__in=shared_pks)
        else:
            return self.none()


class ModelEntity(Entity):
    entity_type = Entity.ENTITY_TYPE_MODEL
    other_type = Entity.ENTITY_TYPE_PROTOCOL
    display_type = 'model'
    url_type = 'model'

    objects = EntityManager()

    class Meta:
        proxy = True
        verbose_name_plural = 'Model entities'


class ProtocolEntity(Entity):
    entity_type = Entity.ENTITY_TYPE_PROTOCOL
    other_type = Entity.ENTITY_TYPE_MODEL
    display_type = 'protocol'
    url_type = 'protocol'

    objects = EntityManager()

    class Meta:
        proxy = True
        verbose_name_plural = 'Protocol entities'

    # The name of a (possibly ephemeral) file containing documentation for the protocol
    README_NAME = 'readme.md'

    def analyse_new_version(self, commit):
        """Hook called when a new version has been created successfully.

        Parses the main protocol file to look for documentation and extracts it into
        an ephemeral readme.md file, if such a file does not already exist.

        This isn't very intelligent or efficient - it's just a proof-of-concept of the
        ephemeral file approach.

        We also submit a Celery job to do further processing. Eventually this task will
        also extract the readme for us.

        :param entity: the entity which has had a new version added
        :param commit: a `Commit` object for the new version
        """
        from .processing import submit_check_protocol_task
        if self.README_NAME not in commit.filenames:
            main_file_name = commit.master_filename
            if main_file_name is None:
                return  # TODO: Add error to errors.txt instead!
            main_file = commit.get_blob(main_file_name)
            if main_file is None:
                return  # TODO: Add error to errors.txt instead!
            content = main_file.data_stream.read()
            header_start = content.find(b'documentation')
            doc_start = content.find(b'{', header_start)
            doc_end = content.find(b'}', doc_start)
            if doc_start >= 0 and doc_end > doc_start:
                doc = content[doc_start + 1:doc_end]
                # Create ephemeral file
                commit.add_ephemeral_file(self.README_NAME, doc)
        submit_check_protocol_task(self, commit.sha)


class EntityFile(models.Model):
    entity = models.ForeignKey(Entity, related_name='files')
    upload = models.FileField(upload_to='uploads')
    original_name = models.CharField(max_length=255)

    def __str__(self):
        return self.original_name


class AnalysisTask(models.Model):
    """
    A celery task analysing an entity version.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity = models.ForeignKey(Entity, related_name='analysis_tasks')
    version = models.CharField(max_length=40)

    class Meta:
        # Don't analyse the same entity version twice at the same time!
        unique_together = ['entity', 'version']
