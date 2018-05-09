import io
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import pytest

from core.combine import (
    ArchiveReader,
    ArchiveWriter,
    ManifestReader,
    ManifestWriter,
)


@pytest.fixture
def writer():
    return ManifestWriter()


@pytest.fixture
def reader():
    return ManifestReader()


@pytest.fixture
def manifest():
    return (
        '<omexManifest xmlns="http://identifiers.org/combine.specifications/omex-manifest">'
        '<content format="txt" location="main.txt" master="true" />'
        '<content format="txt" location="test.txt" master="false" />'
        '</omexManifest>'
    )


@pytest.fixture
def zipped_archive(manifest):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as input_zip:
        input_zip.writestr('manifest.xml', manifest)
        input_zip.writestr('main.txt', 'main file')
        input_zip.writestr('test.txt', 'other file')

    archive.seek(0)
    return archive


class TestManifestWriter:
    def test_starts_with_no_files(self, writer):
        assert writer._files == []

    def test_add_file_with_format(self, writer):
        writer.add_file('file.cellml', fmt='cellml')
        assert ('file.cellml', 'cellml', False) in writer._files

    def test_add_file_with_combine_format(self, writer):
        writer.add_file('file.cellml', combine_format='cellml')
        assert (
            ('file.cellml', 'http://identifiers.org/combine.specifications/cellml', False)
            in writer._files
        )

    def test_add_file_with_mime_type(self, writer):
        writer.add_file('file.cellml', mime_type='application/cellml+xml')
        assert (
            ('file.cellml', 'http://purl.org/NET/mediatypes/application/cellml+xml', False)
            in writer._files
        )

    def test_chooses_combine_type_if_available(self, writer):
        writer.add_file('file.cellml')
        assert (
            ('file.cellml', 'http://identifiers.org/combine.specifications/cellml', False)
            in writer._files
        )

    def test_chooses_mime_type_if_no_spec_given(self, writer):
        writer.add_file('file.txt')
        assert ('file.txt', 'http://purl.org/NET/mediatypes/text/plain', False) in writer._files

    def test_empty_file_type_if_not_available(self, writer):
        writer.add_file('file.nonexistent_type')
        assert ('file.nonexistent_type', '', False) in writer._files

    def test_xml_doc(self, writer, manifest):
        writer.add_file('main.txt', fmt='txt', is_master=True)
        writer.add_file('test.txt', fmt='txt')

        doc = ET.tostring(writer.xml_doc.getroot()).decode()
        assert doc == manifest


class TestManifestReader:
    def test_starts_with_empty_root(self, reader):
        assert reader._root == []

    def test_master_filename(self, reader, manifest):
        reader._root = ET.fromstring(manifest)
        assert reader.master_filename == 'main.txt'

    def test_lists_files(self, reader, manifest):
        reader._root = ET.fromstring(manifest)
        files = reader.files
        assert len(files) == 2
        assert files[0].name == 'main.txt'
        assert files[0].fmt == 'txt'
        assert files[0].is_master
        assert files[1].name == 'test.txt'
        assert files[1].fmt == 'txt'
        assert not files[1].is_master


class TestArchiveReader:
    def test_lists_files(self, zipped_archive):
        files = ArchiveReader(zipped_archive).files

        assert len(files) == 2
        assert files[0].name == 'main.txt'
        assert files[0].size == 9
        assert files[1].name == 'test.txt'
        assert files[1].size == 10

    def test_open_file(self, reader, zipped_archive):
        reader = ArchiveReader(zipped_archive)
        assert reader.open_file('main.txt').read() == b'main file'


class TestWriteArchive:
    def test_writes_archive(self):
        with tempfile.NamedTemporaryFile() as fn:
            fn.write(b'file contents')
            writer = ArchiveWriter()
            archive = writer.write([(fn.name, 'test.txt')])

            assert zipfile.ZipFile(archive).namelist() == ['test.txt']
