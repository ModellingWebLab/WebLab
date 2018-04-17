import xml.etree.ElementTree as ET

import pytest

from core.combine import ManifestReader, ManifestWriter


@pytest.fixture
def writer():
    return ManifestWriter()


@pytest.fixture
def reader():
    return ManifestReader()


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

    def test_xml_doc(self, writer):
        writer.add_file('main.txt', fmt='txt', is_master=True)
        writer.add_file('test.txt', fmt='txt')

        doc = ET.tostring(writer.xml_doc.getroot()).decode()
        assert doc == (
            '<omexManifest xmlns="http://identifiers.org/combine.specifications/omex-manifest">'
            '<content format="txt" location="main.txt" master="true" />'
            '<content format="txt" location="test.txt" master="false" />'
            '</omexManifest>'
        )


class TestManifestReader:
    def test_starts_with_empty_root(self, reader):
        assert reader._root == []

    def test_master_filename(self, reader):
        doc = (
            '<omexManifest xmlns="http://identifiers.org/combine.specifications/omex-manifest">'
            '<content format="txt" location="main.txt" master="true" />'
            '<content format="txt" location="test.txt" master="false" />'
            '</omexManifest>'
        )
        reader._root = ET.fromstring(doc)
        assert reader.master_filename == 'main.txt'
