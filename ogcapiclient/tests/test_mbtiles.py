import os
import sqlite3
import tempfile
import unittest

from ogcapiclient.core.exceptions import MbTilesError
from ogcapiclient.core.mbtiles import MbTilesWriter


class TestMbBTilesWriter(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.file_path = os.path.join(self.tmp_dir.name, "test.mbtiles")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _read_metadata(self) -> list[tuple]:
        """Helper to get metadata rows from the MBTiles."""
        conn = sqlite3.connect(self.file_path)
        sql = "SELECT name, value FROM metadata"
        rows = conn.execute(sql).fetchall()
        conn.close()
        return rows

    def _read_tiles(self) -> list[tuple]:
        """Helper to get tiles rows from the MBTiles."""
        conn = sqlite3.connect(self.file_path)
        sql = "SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles"
        rows = conn.execute(sql).fetchall()
        conn.close()
        return rows

    def test_create_succeeds_for_new_file(self):
        writer = MbTilesWriter(self.file_path)
        self.assertTrue(writer.create())
        self.assertTrue(os.path.exists(self.file_path))
        writer.close()

    def test_create_initializes_file_with_tables(self):
        writer = MbTilesWriter(self.file_path)
        writer.create()

        conn = sqlite3.connect(self.file_path)
        sql = "SELECT name FROM sqlite_master WHERE type='table'"
        result = conn.execute(sql).fetchall()
        tables = {row[0] for row in result}
        conn.close()
        writer.close()

        self.assertIn("metadata", tables)
        self.assertIn("tiles", tables)

    def test_create_returns_true_on_existing_empty_file(self):
        with open(self.file_path, "wb") as f:
            f.write(b"")

        writer = MbTilesWriter(self.file_path)
        self.assertTrue(writer.create())

    def test_create_returns_false_on_existing_nonempty_file(self):
        with open(self.file_path, "wb") as f:
            f.write(b"test-data")

        writer = MbTilesWriter(self.file_path)
        self.assertFalse(writer.create())
        self.assertIsNone(writer.conn)

    def test_create_returns_false_if_called_twice(self):
        writer = MbTilesWriter(self.file_path)
        self.assertTrue(writer.create())
        self.assertFalse(writer.create())
        writer.close()

    def test_set_metadata_value_before_create_raises(self):
        writer = MbTilesWriter(self.file_path)
        with self.assertRaises(MbTilesError):
            writer.set_metadata_value("name", "test")

    def test_set_tile_data_before_create_raises(self):
        writer = MbTilesWriter(self.file_path)
        with self.assertRaises(MbTilesError):
            writer.set_tile_data(0, 0, 0, b"data")

    def test_set_metadata_value_after_close_raises(self):
        writer = MbTilesWriter(self.file_path)
        writer.create()
        writer.close()
        with self.assertRaises(MbTilesError):
            writer.set_metadata_value("name", "test")

    def test_set_tile_data_after_close_raises(self):
        writer = MbTilesWriter(self.file_path)
        writer.create()
        writer.close()
        with self.assertRaises(MbTilesError):
            writer.set_tile_data(0, 0, 0, b"data")

    def test_close_is_idempotent(self):
        writer = MbTilesWriter(self.file_path)
        writer.create()
        writer.close()
        self.assertIsNone(writer.conn)
        writer.close()
        self.assertIsNone(writer.conn)

    def test_close_without_create_does_not_raise(self):
        writer = MbTilesWriter(self.file_path)
        writer.close()

    def test_set_metadata_value_persists(self):
        writer = MbTilesWriter(self.file_path)
        writer.create()
        writer.set_metadata_value("name", "collection")
        writer.set_metadata_value("format", "pbf")

        rows = self._read_metadata()
        self.assertIn(("name", "collection"), rows)
        self.assertIn(("format", "pbf"), rows)

        writer.close()

    def test_set_metadata_value_allows_duplicate_keys(self):
        writer = MbTilesWriter(self.file_path)
        writer.create()
        writer.set_metadata_value("name", "first")
        writer.set_metadata_value("name", "second")

        rows = self._read_metadata()
        names = [r for r in rows if r[0] == "name"]
        self.assertEqual(len(names), 2)

        writer.close()

    def test_set_tile_data_persists(self):
        writer = MbTilesWriter(self.file_path)
        writer.create()
        writer.set_tile_data(1, 2, 3, b"data")

        rows = self._read_tiles()
        self.assertEqual(len(rows), 1)
        z, x, y, data = rows[0]
        self.assertEqual((z, x, y), (1, 2, 3))
        self.assertEqual(data, b"data")

        writer.close()

    def test_set_tile_data_overwrites_existing_tile(self):
        writer = MbTilesWriter(self.file_path)
        writer.create()
        writer.set_tile_data(1, 2, 3, b"original")
        writer.set_tile_data(1, 2, 3, b"updated")

        rows = self._read_tiles()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][3], b"updated")

        writer.close()

    def test_set_tile_data_multiple_distinct_tiles(self):
        writer = MbTilesWriter(self.file_path)
        writer.create()
        writer.set_tile_data(0, 0, 0, b"a")
        writer.set_tile_data(1, 0, 0, b"b")
        writer.set_tile_data(1, 1, 0, b"c")

        rows = self._read_tiles()
        self.assertEqual(len(rows), 3)

        writer.close()

    def test_set_tile_data_committed_immediately(self):
        writer = MbTilesWriter(self.file_path)
        writer.create()
        writer.set_tile_data(5, 10, 15, b"data")

        conn = sqlite3.connect(self.file_path)
        sql = "SELECT tile_data FROM tiles WHERE zoom_level=5 AND tile_column=10 AND tile_row=15"
        row = conn.execute(sql).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], b"data")

        writer.close()


if __name__ == "__main__":
    unittest.main()
