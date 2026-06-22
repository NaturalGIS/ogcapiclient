"""Simple MBTiles writer."""

import os
import sqlite3

from ogcapiclient.core.exceptions import MbTilesError


class MbTilesWriter:
    """Class for writing MBTiles."""

    def __init__(self, file_path: str) -> None:
        """Constructs MBTiles writer.

        :param file_path: Path to the file to write.
        :type file_path: str
        """
        self.file_path = file_path
        self.conn = None

    def create(self) -> bool:
        """Creates a new MBTiles file and initializes it with metadata and tiles tables.

        :returns: Returns true on success. If the file exists already, returns false.
        :rtype: bool
        """
        if self.conn is not None:
            return False

        if os.path.exists(self.file_path) and os.path.getsize(self.file_path) > 0:
            return False

        self.conn = sqlite3.connect(self.file_path)

        sql = (
            "BEGIN;"
            "CREATE TABLE metadata (name text, value text);"
            "CREATE TABLE tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob);"
            "CREATE UNIQUE INDEX tile_index on tiles (zoom_level, tile_column, tile_row);"
            "COMMIT;"
        )
        self.conn.executescript(sql)
        return True

    def set_metadata_value(self, key: str, value: str) -> None:
        """Sets metadata value for the given key.

        :param key: Metadata key.
        :type key: str
        :param value: Metadata value.
        :type value: str

        :raises MbTilesError: If called before create() or after close().
        """
        if self.conn is None:
            raise MbTilesError("MBTiles writer is not initialized.")

        params = (key, value)
        self.conn.execute("INSERT INTO metadata VALUES (?, ?)", params)
        self.conn.commit()

    def set_tile_data(self, z: int, x: int, y: int, data: bytes) -> None:
        """Adds tile data for the given tile coordinates. If a tile already
        exists for the given coordinates, it is overwritten.

        :param z: Zoom level.
        :type z: int
        :param x: Tile column.
        :type x: int
        :param y: Tile row.
        :type y: int
        :param data: Tile data.
        :type data: bytes

        :raises MbTilesError: If called before create() or after close().
        """
        if self.conn is None:
            raise MbTilesError("MBTiles writer is not initialized.")

        params = (z, x, y, data)
        self.conn.execute("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?)", params)
        self.conn.commit()

    def close(self) -> None:
        """Closes the MBTiles file."""
        if self.conn is None:
            return

        self.conn.close()
        self.conn = None
