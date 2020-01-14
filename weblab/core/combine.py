import mimetypes
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path


COMBINE_NS = 'http://identifiers.org/combine.specifications/'
MANIFEST_NS = '%somex-manifest' % COMBINE_NS
MIME_NS = 'http://purl.org/NET/mediatypes/'

MANIFEST_FILENAME = 'manifest.xml'

# Spec says to prefer identifiers.org URI over media types.
# (http://co.mbine.org/specifications/omex.version-1.pdf)
# combine.specifications as per http://co.mbine.org/standards/specifications/
COMBINE_FORMATS = {
    'cellml': 'cellml',
}


class ManifestWriter:
    """
    Writer for COMBINE archive manifest file
    """
    def __init__(self):
        self._files = []

    @staticmethod
    def identify_combine_format(path):
        """
        Determine combine.specifications format of a file

        :path: Path of target file
        :return: namespaced format if identified, empty string otherwise
        """
        extension = ''.join(Path(path).suffixes)[1:]
        fmt = COMBINE_FORMATS.get(extension, '')
        return COMBINE_NS + fmt if fmt else ''

    @staticmethod
    def identify_mime_type(path):
        """
        Determine mime_type for a file

        :path: Path of target file
        :return: namespaced mime type if identified, empty string otherwise
        """
        # make csv mapping explicit (in windows tests, defaults to excel)
        mimetypes.add_type('text/csv', '.csv')

        fmt, _ = mimetypes.guess_type(path)
        return MIME_NS + fmt if fmt else ''

    def add_file(self, path, *, is_master=False,
                 fmt='', mime_type='', combine_format=''):
        """
        Add file to manifest

        :param path: Filename, relative to root of archive
        :param fmt: File format as string
        :param mime_type: Mime type as string
        :param combine_format: combine format as string
        :param is_master: True if this is master file, False if not

        Caller should specify only one of `fmt`, `mime_type` or `combine_format`.
        If none of these is specified, the method will attempt to identify format.
        """
        format_ = fmt
        if fmt:
            format_ = fmt
        elif combine_format:
            format_ = COMBINE_NS + combine_format
        elif mime_type:
            format_ = MIME_NS + mime_type
        else:
            format_ = self.identify_combine_format(path) or self.identify_mime_type(path)

        self._files.append((path, format_, is_master))

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
                    'location': path,
                    'format': fmt,
                    'master': 'true' if is_master else 'false'
                }
            )

        return ET.ElementTree(root)

    def write(self, path):
        """
        Write manifest file

        :param path: Absolute path of manifest file
        """
        return self.xml_doc.write(path, encoding='UTF-8', xml_declaration=True)


class ArchiveFile:
    """
    A file within a COMBINE archive
    """
    def __init__(self, name, fmt, is_master=False, size=None):
        self.name = name
        self.fmt = fmt
        self.is_master = is_master
        self.size = size


class ManifestReader:
    """
    Reader for COMBINE manifest file
    """
    def __init__(self):
        self._root = []

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

    @property
    def files(self):
        """
        List of files in manifest

        :return: iterable of ArchiveFile objects, without size information
        """
        return [
            ArchiveFile(
                name=child.attrib['location'].lstrip('/'),
                fmt=child.attrib['format'],
                is_master=child.attrib.get('master') == 'true',
            )
            for child in self._root
        ]


class ArchiveReader:
    """
    Read in a COMBINE archive
    """
    def __init__(self, archive):
        """
        Create an archive reader

        @param archive - filename or file-like object of archive
        """
        self._zip_archive = zipfile.ZipFile(archive)

    @property
    def files(self):
        """
        List of files in the archive

        :return: iterable of ArchiveFile objects, augmented with size information
        """
        with self._zip_archive as archive:
            reader = ManifestReader()
            reader.read(archive.open(MANIFEST_FILENAME))
            files = reader.files
            for f in files:
                f.size = archive.getinfo(f.name).file_size
            return files

    def open_file(self, name):
        with self._zip_archive as archive:
            return archive.open(name)


class ArchiveWriter:
    """
    Write a COMBINE archive
    """
    def __init__(self):
        self._memfile = BytesIO()
        self._zip_archive = zipfile.ZipFile(self._memfile, 'w', zipfile.ZIP_DEFLATED)

    def write(self, file_data):
        """
        Write files to a combine archive

        Assumes manifest already exists in the file collection

        @param file_data iterable of (filename, contents, date_time) tuples
            where filename is the filename/path to use in the zipfile,
            contents is the file content (as str or bytes or file-like), and
            date_time (a datetime.datetime instance) is the file modification time to store
        @return BytesIO object to which archive data has been written
        """
        for filename, contents, date_time in file_data:
            info = zipfile.ZipInfo(filename, date_time.timetuple())
            if not isinstance(contents, (str, bytes)):
                contents = contents.read()
            self._zip_archive.writestr(info, contents)
        self._zip_archive.close()
        self._memfile.seek(0)
        return self._memfile
