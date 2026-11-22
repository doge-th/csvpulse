import tempfile
import unittest
from pathlib import Path

from csvpulse.profile import profile_file

BASIC = """id,customer,amount,status,note
1,Alice,120.50,paid,fast ship
2,Bob,,pending,
3,Alice,88,paid,
4,Cara,-3.25,void,refund
1,Alice,120.50,paid,fast ship
"""


class TestProfile(unittest.TestCase):
    def _file(self, text: str, suffix: str = ".csv") -> Path:
        f = Path(tempfile.mkdtemp()) / f"data{suffix}"
        f.write_text(text)
        return f

    def test_basic_stats(self):
        prof = profile_file(self._file(BASIC))
        self.assertEqual(prof.rows, 5)
        self.assertEqual([c.name for c in prof.columns],
                         ["id", "customer", "amount", "status", "note"])
        self.assertEqual(prof.columns[0].kind, "int")
        self.assertEqual((prof.columns[0].num_min, prof.columns[0].num_max), (1, 4))
        self.assertEqual(prof.columns[0].unique, 4)
        self.assertEqual(prof.columns[1].kind, "text")
        self.assertEqual(prof.columns[1].unique, 3)  # Alice, Bob, Cara
        self.assertEqual(prof.columns[1].top[0], ("Alice", 3))
        self.assertEqual(prof.columns[2].kind, "float")
        self.assertEqual(prof.columns[2].empty, 1)
        self.assertEqual(prof.columns[2].num_min, -3.25)
        self.assertAlmostEqual(prof.columns[2].num_max, 120.50)
        self.assertEqual(prof.duplicates, 1)  # rows 1 and 5
        self.assertEqual(prof.ragged, 0)

    def test_empty_column_is_empty_kind(self):
        prof = profile_file(self._file("a,b\n1,\n2,\n"))
        self.assertEqual(prof.columns[1].kind, "empty")
        self.assertEqual(prof.columns[1].fill, 0.0)

    def test_mixed_column_is_text(self):
        prof = profile_file(self._file("a\n12\n3.5\nhello\n"))
        self.assertEqual(prof.columns[0].kind, "text")

    def test_ragged_rows(self):
        prof = profile_file(self._file("a,b\n1,2\n3,4,5\n"))
        self.assertEqual(prof.ragged, 1)
        self.assertEqual(prof.ragged_lines, [2])
        self.assertEqual(prof.rows, 2)  # ragged row still counted
        self.assertEqual(prof.columns[0].total, 1)  # excluded from stats

    def test_semicolon_sniffed(self):
        prof = profile_file(self._file("a;b\n1;2\n3;4\n"))
        self.assertTrue(prof.delimiter_sniffed)
        self.assertEqual(prof.delimiter, ";")
        self.assertEqual(prof.n_columns, 2)

    def test_explicit_delimiter(self):
        prof = profile_file(self._file("a\tb\n1\t2\n"), delimiter="\t")
        self.assertFalse(prof.delimiter_sniffed)
        self.assertEqual(prof.delimiter, "\t")

    def test_utf8_sig_bom(self):
        f = Path(tempfile.mkdtemp()) / "bom.csv"
        f.write_bytes("a,b\n1,é\n".encode("utf-8-sig"))
        prof = profile_file(f)
        self.assertEqual(prof.encoding, "UTF-8-SIG")
        self.assertFalse(prof.encoding_lossy)

    def test_latin1_fallback_is_lossy(self):
        f = Path(tempfile.mkdtemp()) / "latin.csv"
        f.write_bytes(b"a,b\n1,caf\xe9\n")
        prof = profile_file(f)
        self.assertEqual(prof.encoding, "latin-1")
        self.assertTrue(prof.encoding_lossy)
        self.assertEqual(prof.columns[1].top[0][0], "café")

    def test_explicit_encoding(self):
        f = Path(tempfile.mkdtemp()) / "gbk.csv"
        f.write_bytes("a,b\n1,中文\n".encode("gbk"))
        prof = profile_file(f, encoding="gbk")
        self.assertEqual(prof.encoding, "gbk")
        self.assertFalse(prof.encoding_lossy)

    def test_no_header_mode(self):
        prof = profile_file(self._file("1,2\n3,4\n"), has_header=False)
        self.assertEqual(prof.header, ["col1", "col2"])
        self.assertEqual(prof.rows, 2)
        self.assertEqual(prof.columns[0].num_max, 3)

    def test_unique_counts_stop_at_cap(self):
        under = profile_file(self._file(
            "a\n" + "\n".join(f"v{i}" for i in range(100)) + "\n"))
        self.assertEqual(under.columns[0].unique, 100)
        self.assertFalse(under.columns[0].unique_capped)

        over = profile_file(self._file(
            "a\n" + "\n".join(f"v{i}" for i in range(10001)) + "\n"))
        self.assertTrue(over.columns[0].unique_capped)
        self.assertEqual(over.columns[0].unique, 0)  # memory released at cap


if __name__ == "__main__":
    unittest.main()
