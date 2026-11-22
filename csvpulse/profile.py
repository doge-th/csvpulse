"""Reading and profiling: encoding/delimiter sniffing, per-column stats."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

UNIQUE_CAP = 10_000          # stop counting distinct values past this
DUPSCAN_ROW_CAP = 1_000_000  # skip duplicate counting past this
TOP_VALUES = 3


@dataclass
class ColumnStats:
    name: str
    total: int = 0            # non-header rows seen for this column
    empty: int = 0
    unique: int = 0           # distinct non-empty values (0 when capped)
    unique_capped: bool = False
    kind: str = "text"        # int | float | text | empty
    num_min: float | None = None
    num_max: float | None = None
    mean: float | None = None
    top: list[tuple[str, int]] = field(default_factory=list)

    @property
    def fill(self) -> float:
        return (self.total - self.empty) / self.total if self.total else 0.0


@dataclass
class Profile:
    path: str
    encoding: str = "utf-8"
    encoding_lossy: bool = False  # fell back to latin-1
    delimiter: str = ","
    delimiter_sniffed: bool = False
    header: list[str] = field(default_factory=list)
    rows: int = 0
    ragged: int = 0
    ragged_lines: list[int] = field(default_factory=list)
    duplicates: int = 0
    duplicate_scan_skipped: bool = False
    columns: list[ColumnStats] = field(default_factory=list)

    @property
    def n_columns(self) -> int:
        return len(self.columns)


class _Column:
    """Streaming accumulator for one column."""

    def __init__(self, name: str):
        self.name = name
        self.total = 0
        self.empty = 0
        self.distinct: set[str] = set()
        self.counter: Counter[str] = Counter()
        self.capped = False
        self.all_int = True
        self.all_num = True
        self.n_count = 0
        self.n_sum = 0.0
        self.n_min: float | None = None
        self.n_max: float | None = None

    def feed(self, value: str) -> None:
        self.total += 1
        if value == "":
            self.empty += 1
            return
        if not self.capped:
            self.counter[value] += 1
            if value not in self.distinct:
                self.distinct.add(value)
                if len(self.distinct) >= UNIQUE_CAP:
                    self.capped = True
                    self.distinct.clear()
                    self.counter.clear()
        if self.all_num:
            try:
                n = int(value)
            except ValueError:
                self.all_int = False
                try:
                    n = float(value)
                except ValueError:
                    self.all_num = False
                    return
            self.n_count += 1
            self.n_sum += n
            self.n_min = n if self.n_min is None else min(self.n_min, n)
            self.n_max = n if self.n_max is None else max(self.n_max, n)

    def finish(self, top_n: int = TOP_VALUES) -> ColumnStats:
        kind = "text"
        if self.total and self.empty == self.total:
            kind = "empty"
        elif self.all_num and self.n_count:
            kind = "int" if self.all_int else "float"
        mn = mx = mean = None
        if self.all_num and self.n_count:
            mn, mx = self.n_min, self.n_max
            mean = self.n_sum / self.n_count
            if self.all_int:
                mn, mx = int(mn), int(mx)
        return ColumnStats(
            name=self.name, total=self.total, empty=self.empty,
            unique=len(self.distinct) if not self.capped else 0,
            unique_capped=self.capped, kind=kind,
            num_min=mn, num_max=mx, mean=mean,
            top=self.counter.most_common(top_n),
        )


def _decode(data: bytes) -> tuple[str, str, bool]:
    """(text, encoding name, lossy) — BOM first, then strict utf-8."""
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig"), "UTF-8-SIG", False
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16"), "UTF-16", False
    try:
        return data.decode("utf-8"), "UTF-8", False
    except UnicodeDecodeError:
        return data.decode("latin-1"), "latin-1", True


def _sniff_delimiter(text: str) -> str | None:
    try:
        return csv.Sniffer().sniff(text[:8192],
                                   delimiters=",;\t|").delimiter
    except csv.Error:
        return None


def profile_file(path: Path, delimiter: str | None = None,
                 encoding: str | None = None, has_header: bool = True,
                 top_n: int = TOP_VALUES) -> Profile:
    """One pass over the file: column stats, ragged rows, duplicate rows."""
    return _profile(path, delimiter, encoding, has_header, top_n)


def _profile(path: Path, delimiter, encoding, has_header, top_n) -> Profile:
    data = path.read_bytes()
    if encoding and encoding.lower() not in ("utf-8", "utf8"):
        enc = encoding
        try:
            text = data.decode(encoding)
            lossy = False
        except UnicodeDecodeError:
            text = data.decode(encoding, "replace")
            lossy = True
    else:
        text, enc, lossy = _decode(data)

    delim = delimiter
    sniffed = False
    if not delim:
        delim = _sniff_delimiter(text)
        sniffed = delim is not None
        delim = delim or ","

    prof = Profile(path=str(path), encoding=enc, encoding_lossy=lossy,
                   delimiter=delim, delimiter_sniffed=sniffed)

    header: list[str] | None = None
    columns: list[_Column] = []
    seen_hashes: set[bytes] = set()

    for row in csv.reader(text.splitlines(), delimiter=delim):
        if header is None:
            if has_header:
                header = row
            else:
                header = [f"col{i + 1}" for i in range(len(row))]
            columns = [_Column(name or "(blank)") for name in header]
            if has_header:
                continue
        prof.rows += 1
        if len(row) != len(columns):
            prof.ragged += 1
            if len(prof.ragged_lines) < 50:
                prof.ragged_lines.append(prof.rows)
            continue  # ragged rows stay out of per-column stats

        if not prof.duplicate_scan_skipped:
            if prof.rows <= DUPSCAN_ROW_CAP:
                h = hashlib.sha1("\x00".join(row).encode("utf-8", "replace")).digest()
                if h in seen_hashes:
                    prof.duplicates += 1
                else:
                    seen_hashes.add(h)
            else:
                prof.duplicate_scan_skipped = True
                seen_hashes.clear()

        for i, value in enumerate(row):
            columns[i].feed(value)

    prof.header = header or []
    prof.columns = [c.finish(top_n) for c in columns]
    return prof
