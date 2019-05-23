
from core.filetypes import get_file_type


def test_get_file_type():
    assert get_file_type('thing.cellml') == 'CellML'
    assert get_file_type('thing.txt') == 'TXTPROTOCOL'
    assert get_file_type('thing.xml') == 'XMLPROTOCOL'
    assert get_file_type('thing.zip') == 'COMBINE archive'
    assert get_file_type('thing.omex') == 'COMBINE archive'
    assert get_file_type('thing.md') == 'MARKDOWN'
    assert get_file_type('thing.csv') == 'CSV'
    assert get_file_type('thing.eps') == 'EPS'
    assert get_file_type('thing.png') == 'PNG'
    assert get_file_type('thing.h5') == 'HDF5'
    assert get_file_type('thing.jpg') == 'Unknown'
