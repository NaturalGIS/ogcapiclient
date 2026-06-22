"""Enumerations shared across the OGC API client GUI."""

from enum import IntEnum


class CollectionModelColumn(IntEnum):
    """Columns of the collections tree."""

    TITLE = 0
    """Collection title column."""
    NAME = 1
    """Collection ID column."""
    TYPE = 2
    """Collection type column."""
    ABSTRACT = 3
    """Collection absttract column."""
