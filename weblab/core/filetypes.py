"""Utility functions & maps for defining key Web Lab file types."""

import os.path


def get_file_type(filename):
    _, ext = os.path.splitext(filename)

    extensions = {
        'cellml': 'CellML',
        'csv': 'CSV',
        'md': 'MARKDOWN',
        'txt': 'TXTPROTOCOL',
        'xml': 'XMLPROTOCOL',
        'zip': 'COMBINE archive',
        'omex': 'COMBINE archive',
        'eps': 'EPS',
        'png': 'PNG',
        'h5': 'HDF5',
    }

    return extensions.get(ext[1:], 'Unknown')
