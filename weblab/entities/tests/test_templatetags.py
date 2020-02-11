import pytest

import entities.templatetags.entities as entity_tags
from core import recipes
from repocache.populate import populate_entity_cache


def test_human_readable_bytes():
    assert entity_tags.human_readable_bytes(0) == '0 Bytes'

    assert entity_tags.human_readable_bytes(512) == '512.00 Bytes'

    assert entity_tags.human_readable_bytes(2**10) == '1.00 KB'
    assert entity_tags.human_readable_bytes(2**10 * 1.5) == '1.50 KB'

    assert entity_tags.human_readable_bytes(2**20) == '1.00 MB'
    assert entity_tags.human_readable_bytes(2**20 * 1.5) == '1.50 MB'

    assert entity_tags.human_readable_bytes(2**30) == '1.00 GB'
    assert entity_tags.human_readable_bytes(2**30 * 1.5) == '1.50 GB'

    assert entity_tags.human_readable_bytes(2**40) == '1.00 TB'
    assert entity_tags.human_readable_bytes(2**40 * 1.5) == '1.50 TB'


def test_file_type():
    assert entity_tags.file_type('thing.cellml') == 'CellML'
    assert entity_tags.file_type('thing.txt') == 'TXTPROTOCOL'
    assert entity_tags.file_type('thing.xml') == 'XMLPROTOCOL'
    assert entity_tags.file_type('thing.zip') == 'COMBINE archive'
    assert entity_tags.file_type('thing.omex') == 'COMBINE archive'
    assert entity_tags.file_type('thing.jpg') == 'Unknown'


@pytest.mark.django_db
def test_model_urls(model_with_version):
    model = model_with_version
    model_version = model.repocache.latest_version
    context = {'current_namespace': 'entities'}

    assert entity_tags.ns_url(context, 'new', 'model') == '/entities/models/new'
    assert entity_tags.entity_url(context, 'detail', model) == '/entities/models/%d' % model.pk
    assert entity_tags.entity_url(context, 'delete', model) == '/entities/models/%d/delete' % model.pk
    assert entity_tags.entity_url(context, 'version_list', model) == '/entities/models/%d/versions/' % model.pk
    assert entity_tags.entity_url(context, 'newversion', model) == '/entities/models/%d/versions/new' % model.pk
    assert (entity_tags.entity_version_url(context, 'version', model, model_version) ==
            '/entities/models/%d/versions/%s' % (model.pk, model_version.sha))
    assert (entity_tags.entity_version_url(context, 'version_json', model, model_version) ==
            '/entities/models/%d/versions/%s/files.json' % (model.pk, model_version.sha))
    assert (entity_tags.url_compare_experiments(model, model_version) ==
            '/entities/models/%d/versions/%s/compare' % (model.pk, model_version.sha))

    assert (entity_tags.entity_version_url(context, 'change_visibility', model, model_version) ==
            '/entities/models/%d/versions/%s/visibility' % (model.pk, model_version.sha))
    assert (entity_tags.tag_version_url(context, model, model_version) ==
            '/entities/tag/%d/%s' % (model.pk, model_version.sha))

    assert entity_tags.url_entity_comparison_base(context, 'model') == '/entities/models/compare'
    assert entity_tags.url_entity_diff_base(context, 'model') == '/entities/models/diff'

    assert (entity_tags.entity_comparison_json_url(context, ['%d:%s' % (model.pk, model_version.sha)], 'model') ==
            '/entities/models/compare/%d:%s/info' % (model.pk, model_version.sha))


@pytest.mark.django_db
def test_protocol_urls(protocol_with_version):
    protocol = protocol_with_version
    protocol_version = protocol.repocache.latest_version
    context = {'current_namespace': 'entities'}

    assert entity_tags.ns_url(context, 'new', 'protocol') == '/entities/protocols/new'
    assert entity_tags.entity_url(context, 'detail', protocol) == '/entities/protocols/%d' % protocol.pk
    assert entity_tags.entity_url(context, 'delete', protocol) == '/entities/protocols/%d/delete' % protocol.pk
    assert entity_tags.entity_url(context, 'version_list', protocol) == '/entities/protocols/%d/versions/' % protocol.pk
    assert (entity_tags.entity_url(context, 'newversion', protocol) ==
            '/entities/protocols/%d/versions/new' % protocol.pk)
    assert (entity_tags.entity_version_url(context, 'version', protocol, protocol_version) ==
            '/entities/protocols/%d/versions/%s' % (protocol.pk, protocol_version.sha))
    assert (entity_tags.entity_version_url(context, 'version_json', protocol, protocol_version) ==
            '/entities/protocols/%d/versions/%s/files.json' %
            (protocol.pk, protocol_version.sha))
    assert (entity_tags.url_compare_experiments(protocol, protocol_version) ==
            '/entities/protocols/%d/versions/%s/compare' % (protocol.pk, protocol_version.sha))
    assert (entity_tags.entity_version_url(context, 'change_visibility', protocol, protocol_version) ==
            '/entities/protocols/%d/versions/%s/visibility' % (protocol.pk, protocol_version.sha))
    assert (entity_tags.tag_version_url(context, protocol, protocol_version) ==
            '/entities/tag/%d/%s' % (protocol.pk, protocol_version.sha))

    assert entity_tags.url_entity_comparison_base(context, 'protocol') == '/entities/protocols/compare'
    assert entity_tags.url_entity_diff_base(context, 'protocol') == '/entities/protocols/diff'

    assert (entity_tags.entity_comparison_json_url(context,
                                                   ['%d:%s' % (protocol.pk, protocol_version.sha)],
                                                   'protocol') ==
            '/entities/protocols/compare/%d:%s/info' % (protocol.pk, protocol_version.sha))


@pytest.mark.django_db
def test_name_of_entity_linked_to_experiment(model_with_version, protocol_with_version):
    model_with_version.repo.tag('v1')
    protocol_with_version.repo.tag('v2')
    populate_entity_cache(model_with_version)
    populate_entity_cache(protocol_with_version)

    exp = recipes.experiment_version.make(
        status='SUCCESS',
        experiment__model=model_with_version,
        experiment__model_version=model_with_version.cachedentity.latest_version,
        experiment__protocol=protocol_with_version,
        experiment__protocol_version=protocol_with_version.cachedentity.latest_version,
    ).experiment

    assert entity_tags.name_of_model(exp) == '%s @ v1' % model_with_version.name
    assert entity_tags.name_of_protocol(exp) == '%s @ v2' % protocol_with_version.name


@pytest.mark.django_db
def test_url_friendly_label(model_with_version, helpers):
    commit = model_with_version.repo.latest_commit
    version = model_with_version.repocache.get_version(commit.sha)

    assert entity_tags._url_friendly_label(model_with_version, version) == commit.sha

    model_with_version.repo.tag('v1')
    populate_entity_cache(model_with_version)

    assert entity_tags._url_friendly_label(model_with_version, version) == 'v1'

    commit2 = helpers.add_version(model_with_version)
    model_with_version.repo.tag('new')
    populate_entity_cache(model_with_version)
    version2 = model_with_version.repocache.get_version(commit2.sha)

    assert entity_tags._url_friendly_label(model_with_version, version2) == commit2.sha

    commit3 = helpers.add_version(model_with_version)
    model_with_version.repo.tag('latest')
    populate_entity_cache(model_with_version)
    version3 = model_with_version.repocache.get_version(commit3.sha)

    assert entity_tags._url_friendly_label(model_with_version, version3) == commit3.sha


@pytest.mark.django_db
def test_url_runexperiments(model_with_version, protocol_with_version):
    model = model_with_version
    model_commit = model.repocache.latest_version
    assert (entity_tags.url_run_experiments(model, model_commit) ==
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, model_commit.sha))

    protocol = protocol_with_version
    protocol_commit = protocol.repocache.latest_version
    assert (entity_tags.url_run_experiments(protocol, protocol_commit) ==
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, protocol_commit.sha))


@pytest.mark.django_db
def test_can_create_entity(anon_user, model_creator, admin_user):
    context = {'user': anon_user}
    assert not entity_tags.can_create_entity(context, 'model')

    context = {'user': model_creator}
    assert entity_tags.can_create_entity(context, 'model')

    context = {'user': admin_user}
    assert entity_tags.can_create_entity(context, 'model')


@pytest.mark.django_db
def test_can_create_version(anon_user, model_creator, admin_user):
    model = recipes.model.make()
    context = {'user': anon_user}
    assert not entity_tags.can_create_version(context, model)

    context = {'user': model_creator}
    assert not entity_tags.can_create_version(context, model)

    context = {'user': admin_user}
    assert entity_tags.can_create_version(context, model)

    model = recipes.model.make(author=model_creator)
    context = {'user': model_creator}
    assert entity_tags.can_create_version(context, model)


@pytest.mark.django_db
def test_can_delete_entity(anon_user, model_creator, admin_user):
    model = recipes.model.make()
    context = {'user': anon_user}
    assert not entity_tags.can_delete_entity(context, model)

    context = {'user': model_creator}
    assert not entity_tags.can_delete_entity(context, model)

    context = {'user': admin_user}
    assert entity_tags.can_delete_entity(context, model)

    model = recipes.model.make(author=model_creator)
    context = {'user': model_creator}
    assert entity_tags.can_delete_entity(context, model)


@pytest.mark.django_db
def test_can_manage_entity(anon_user, model_creator, admin_user):
    model = recipes.model.make()
    context = {'user': anon_user}
    assert not entity_tags.can_manage_entity(context, model)

    context = {'user': model_creator}
    assert not entity_tags.can_manage_entity(context, model)

    context = {'user': admin_user}
    assert entity_tags.can_manage_entity(context, model)

    model = recipes.model.make(author=model_creator)
    context = {'user': model_creator}
    assert entity_tags.can_manage_entity(context, model)
