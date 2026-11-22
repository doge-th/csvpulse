import json
import unittest

from csvpulse.profile import ColumnStats, Profile
from csvpulse.report import fmt_num, render_json, render_markdown, render_table


def _profile():
    prof = Profile(path="data.csv", rows=3, delimiter=",", encoding="UTF-8")
    prof.header = ["id", "amount"]
    prof.columns = [
        ColumnStats(name="id", total=3, kind="int", num_min=1, num_max=3,
                    mean=2.0, unique=3),
        ColumnStats(name="amount", total=3, empty=1, kind="float",
                    num_min=-3.25, num_max=120.5, mean=58.625, unique=2),
    ]
    return prof


class _Opts:
    top = 3


class TestFormatters(unittest.TestCase):
    def test_fmt_num(self):
        self.assertEqual(fmt_num(1200), "1,200")
        self.assertEqual(fmt_num(120.5), "120.5")
        self.assertEqual(fmt_num(None), "?")


class TestRenderers(unittest.TestCase):
    def test_table(self):
        out = render_table(_profile(), _Opts)
        self.assertIn("3 rows", out)
        self.assertIn("[int", out)
        self.assertIn("1…3", out)
        self.assertIn("mean 2.00", out)
        self.assertIn("67% filled · 1 empty", out)
        self.assertIn("No ragged rows", out)

    def test_table_issues(self):
        prof = _profile()
        prof.ragged = 2
        prof.duplicates = 1
        out = render_table(prof, _Opts)
        self.assertIn("Issues", out)
        self.assertIn("2 ragged rows", out)
        self.assertIn("1 duplicate rows", out)

    def test_json_roundtrip(self):
        doc = json.loads(render_json(_profile(), _Opts))
        self.assertEqual(doc["tool"], "csvpulse")
        self.assertEqual(doc["columns"][0]["kind"], "int")
        self.assertEqual(doc["rows"], 3)

    def test_markdown(self):
        out = render_markdown(_profile(), _Opts)
        self.assertIn("## csvpulse — `data.csv`", out)
        self.assertIn("| `id` | int | 100% | 0 | 3 |", out)


if __name__ == "__main__":
    unittest.main()
