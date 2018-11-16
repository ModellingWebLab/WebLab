
class RepoCacheMiss(Exception):
    """
    This is raised when an expected `repocache` object does not exist in the
    database (e.g. a version referenced by SHA)
    """
    pass
