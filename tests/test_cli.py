import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from csvpulse import __version__
from csvpulse.cli import main

BASIC = """id,customer,amount,status
1,Alice,120.50,paid
2,Bob,88.00,pending
3,Alice,-3.25,void
"""


class TestCli(unittest.TestCase):
    def setUp(self):
        self.file = Path(tempfile.mkdtemp()) / "data.csv"
        self.file.write_text(BASIC)

    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_table_report(self):
        code, out, _ = self._run([str(self.file)])
        self.assertEqual(code, 0)
        self.assertIn("3 rows", out)
        self.assertIn("Columns", out)
        self.assertIn("[int", out)
        self.assertIn("[float]", out)
        self.assertIn("No ragged rows", out)
        self.assertIn("Alice (2)", out)

    def test_json_report(self):
        _, out, _ = self._run(["--json", str(self.file)])
        doc = json.loads(out)
        self.assertEqual(doc["tool"], "csvpulse")
        self.assertEqual(doc["version"], __version__)
        self.assertEqual(doc["rows"], 3)
        self.assertEqual(doc["columns"][0]["kind"], "int")
        self.assertEqual(doc["columns"][0]["num_min"], 1)
        self.assertEqual(doc["columns"][1]["top"][0], ["Alice", 2])

    def test_markdown_report(self):
        _, out, _ = self._run(["--markdown", str(self.file)])
        self.assertIn("## csvpulse", out)
        self.assertIn("| column | type | filled | empty | unique | range | top values |", out)

    def test_ragged_reported(self):
        ragged = Path(tempfile.mkdtemp()) / "ragged.csv"
        ragged.write_text("a,b\n1,2\n3,4,5\n")
        _, out, _ = self._run([str(ragged)])
        self.assertIn("1 ragged rows", out)
        self.assertIn("row 2", out)

    def test_missing_file_fails(self):
        code, _, err = self._run(["/nonexistent/nope.csv"])
        self.assertEqual(code, 1)
        self.assertIn("no such file", err)

    def test_delimiter_must_be_single_char(self):
        with self.assertRaises(SystemExit):
            main(["--delimiter", ";;", str(self.file)])

    def test_no_header_flag(self):
        _, out, _ = self._run(["--json", "--no-header", str(self.file)])
        doc = json.loads(out)
        self.assertEqual(doc["header"], ["col1", "col2", "col3", "col4"])
        self.assertEqual(doc["rows"], 4)

    def test_version_flag(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
