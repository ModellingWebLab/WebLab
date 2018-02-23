import xml.etree.ElementTree as ET


MANIFEST_NS = 'http://identifiers.org/combine.specifications/omex-manifest'


class ManifestWriter:
    """
    Writer for COMBINE archive manifest file
    """
    def __init__(self):
        self._files = []

    def add_file(self, path, fmt, is_master):
        """
        Add file to manifest

        :param path: Filename, relative to root of archive
        :param fmt: File format as string
        :param is_master: True if this is master file, False if not
        """
        self._files.append((path, fmt, is_master))

    @property
    def xml_doc(self):
        """
        Manifest XML doc

        :return: `ElementTree` for XML manifest file
        """
        ET.register_namespace('', MANIFEST_NS)
        root = ET.Element('{%s}omexManifest' % MANIFEST_NS)

        for (path, fmt, is_master) in self._files:
            ET.SubElement(
                root,
                '{%s}content' % MANIFEST_NS,
                **{
                    ('{%s}location' % MANIFEST_NS): path,
                    ('{%s}format' % MANIFEST_NS): fmt,
                    ('{%s}master' % MANIFEST_NS): 'true' if is_master else 'false'
                }
            )

        return ET.ElementTree(root)

    def write(self, path):
        """
        Write manifest file

        :param path: Absolute path of manifest file
        """
        return self.xml_doc.write(path, encoding='UTF-8', xml_declaration=True)


class ManifestReader:
    """
    Reader for COMBINE manifest file
    """
    def __init__(self):
        self._root = None

    def read(self, source):
        """
        Read in an XML manifest file

        :param source: Absolute path of manifest file, or file object
        """
        self._root = ET.parse(source).getroot()

    @property
    def master_filename(self):
        """
        Name of master file

        :return: master filename, or None if no master file set
        """
        return next((
            child.attrib['location']
            for child in self._root
            if child.attrib['master'] == 'true'
        ), None)
