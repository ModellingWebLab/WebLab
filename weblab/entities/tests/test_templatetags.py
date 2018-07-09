from datetime import datetime

import pytest

import entities.templatetags.entities as entity_tags
from core import recipes


def test_as_datetime():
    dt = entity_tags.as_datetime(1530628582)
    assert dt == datetime(2018, 7, 3, 14, 36, 22)


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
def test_entity_urls(model_with_version, protocol_with_version):
    model = model_with_version
    protocol = protocol_with_version
    model_version = model.repo.latest_commit
    protocol_version = protocol.repo.latest_commit

    assert entity_tags.url_new('model') == '/entities/models/new'
    assert entity_tags.url_entity(model) == '/entities/models/%d' % model.pk
    assert entity_tags.url_delete(model) == '/entities/models/%d/delete' % model.pk
    assert entity_tags.url_versions(model) == '/entities/models/%d/versions/' % model.pk
    assert entity_tags.url_newversion(model) == '/entities/models/%d/versions/new' % model.pk
    assert (entity_tags.url_version(model, model_version) ==
            '/entities/models/%d/versions/%s' % (model.pk, model_version.hexsha))
    assert (entity_tags.url_version_json(model, model_version) ==
            '/entities/models/%d/versions/%s/files.json' % (model.pk, model_version.hexsha))
    assert (entity_tags.url_version_compare(model, model_version) ==
            '/entities/models/%d/versions/%s/compare' % (model.pk, model_version.hexsha))
    assert (entity_tags.url_tag_version(model, model_version) ==
            '/entities/tag/%d/%s' % (model.pk, model_version.hexsha))

    assert entity_tags.url_new('protocol') == '/entities/protocols/new'
    assert entity_tags.url_entity(protocol) == '/entities/protocols/%d' % protocol.pk
    assert entity_tags.url_delete(protocol) == '/entities/protocols/%d/delete' % protocol.pk
    assert entity_tags.url_versions(protocol) == '/entities/protocols/%d/versions/' % protocol.pk
    assert (entity_tags.url_newversion(protocol) ==
            '/entities/protocols/%d/versions/new' % protocol.pk)
    assert (entity_tags.url_version(protocol, protocol_version) ==
            '/entities/protocols/%d/versions/%s' % (protocol.pk, protocol_version.hexsha))
    assert (entity_tags.url_version_json(protocol, protocol_version) ==
            '/entities/protocols/%d/versions/%s/files.json' %
            (protocol.pk, protocol_version.hexsha))
    assert (entity_tags.url_version_compare(protocol, protocol_version) ==
            '/entities/protocols/%d/versions/%s/compare' % (protocol.pk, protocol_version.hexsha))
    assert (entity_tags.url_tag_version(protocol, protocol_version) ==
            '/entities/tag/%d/%s' % (protocol.pk, protocol_version.hexsha))


@pytest.mark.django_db
def test_name_of_entity_linked_to_experiment(model_with_version, protocol_with_version):
    model_with_version.repo.tag('v1')
    protocol_with_version.repo.tag('v2')

    exp = recipes.experiment_version.make(
        status='SUCCESS',
        experiment__model=model_with_version,
        experiment__model_version=model_with_version.repo.latest_commit.hexsha,
        experiment__protocol=protocol_with_version,
        experiment__protocol_version=protocol_with_version.repo.latest_commit.hexsha,
    ).experiment

    assert entity_tags.name_of_model(exp) == '%s @ v1' % model_with_version.name
    assert entity_tags.name_of_protocol(exp) == '%s @ v2' % protocol_with_version.name


@pytest.mark.django_db
def test_url_friendly_label(model_with_version, helpers):
    commit = model_with_version.repo.latest_commit
    assert entity_tags._url_friendly_label(model_with_version, commit) == commit.hexsha

    model_with_version.repo.tag('v1')
    assert entity_tags._url_friendly_label(model_with_version, commit) == 'v1'

    commit2 = helpers.add_version(model_with_version)
    model_with_version.repo.tag('new')
    assert entity_tags._url_friendly_label(model_with_version, commit2) == commit2.hexsha

    commit3 = helpers.add_version(model_with_version)
    model_with_version.repo.tag('latest')
    assert entity_tags._url_friendly_label(model_with_version, commit3) == commit3.hexsha
