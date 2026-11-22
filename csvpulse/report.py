"""Rendering: table (ANSI, NO_COLOR aware), JSON, Markdown."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict

from . import __version__
from .profile import Profile


def _ansi_enabled() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


class Ansi:
    def __init__(self, enabled: bool = None):
        self.on = _ansi_enabled() if enabled is None else enabled

    def _wrap(self, code: int, s: str) -> str:
        return f"\x1b[{code}m{s}\x1b[0m" if self.on else s

    def bold(self, s): return self._wrap(1, s)
    def dim(self, s): return self._wrap(2, s)
    def red(self, s): return self._wrap(31, s)
    def green(self, s): return self._wrap(32, s)
    def yellow(self, s): return self._wrap(33, s)
    def cyan(self, s): return self._wrap(36, s)


def fmt_num(v) -> str:
    if v is None:
        return "?"
    if isinstance(v, int):
        return f"{v:,}"
    return f"{v:g}"


def _column_line(a: Ansi, col) -> str:
    bits = []
    fill = f"{col.fill:.0%} filled"
    if col.empty:
        bits.append(f"{fill} · {col.empty} empty")
    else:
        bits.append(fill)
    if col.unique_capped:
        bits.append(f"≥{col.unique}+ unique" if col.unique else "unique ≥10k")
    else:
        bits.append(f"{col.unique:,} unique")
    if col.kind in ("int", "float") and col.num_min is not None:
        bits.append(f"{fmt_num(col.num_min)}…{fmt_num(col.num_max)}"
                    + (f" · mean {col.mean:.2f}" if col.mean is not None else ""))
    if col.top:
        tops = ", ".join(f"{repr(v) if len(v) > 24 else v} ({n})"
                         for v, n in col.top)
        bits.append(f"top: {tops}")
    name = col.name if len(col.name) <= 24 else col.name[:23] + "…"
    return f"  {a.bold(f'{name:<24}')} [{col.kind:<5}] " + " · ".join(bits)


def render_table(prof: Profile, opts) -> str:
    a = Ansi()
    out = []
    enc = prof.encoding + (" (lossy)" if prof.encoding_lossy else "")
    delim = prof.delimiter
    delim_disp = {"\t": "\\t"}.get(delim, delim)
    out.append(a.bold(f"csvpulse v{__version__}")
               + a.dim(f"  ·  {prof.path}  ·  {prof.rows:,} rows"
                       f" · {prof.n_columns} columns"
                       f" · delimiter {delim_disp!r}"
                       + (a.dim(" (sniffed)") if prof.delimiter_sniffed else "")
                       + f" · {enc}"))
    out.append("")
    out.append(a.cyan("Columns"))
    if not prof.columns:
        out.append(a.dim("  (no columns — empty file?)"))
    for col in prof.columns:
        out.append(_column_line(a, col))

    out.append("")
    issues = []
    if prof.ragged:
        where = f", first at data row {prof.ragged_lines[0]}" if prof.ragged_lines else ""
        issues.append(a.red(f"  {prof.ragged} ragged rows (field count ≠ header){where}"))
    if prof.duplicates:
        issues.append(a.yellow(f"  {prof.duplicates} duplicate rows"))
    if prof.duplicate_scan_skipped:
        issues.append(a.dim("  duplicate scan skipped past 1,000,000 rows"))
    if prof.encoding_lossy:
        issues.append(a.yellow("  decoding was lossy (latin-1 fallback) — "
                               "try --encoding"))
    if issues:
        out.append(a.cyan("Issues"))
        out.extend(issues)
    else:
        out.append(a.green("No ragged rows, no duplicates, clean UTF-8."))
    return "\n".join(out)


def render_json(prof: Profile, opts) -> str:
    doc = asdict(prof)
    doc["tool"] = "csvpulse"
    doc["version"] = __version__
    return json.dumps(doc, indent=2, ensure_ascii=False)


def render_markdown(prof: Profile, opts) -> str:
    lines = [
        f"## csvpulse — `{prof.path}`",
        "",
        f"**{prof.rows:,} rows · {prof.n_columns} columns ·"
        f" delimiter `{prof.delimiter}` · {prof.encoding}**",
        "",
        "| column | type | filled | empty | unique | range | top values |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for col in prof.columns:
        rng = (f"{fmt_num(col.num_min)}…{fmt_num(col.num_max)}"
               if col.kind in ("int", "float") and col.num_min is not None else "—")
        tops = ", ".join(f"{v} ({n})" for v, n in col.top) or "—"
        tops = tops.replace("|", "\\|")
        lines.append(
            f"| `{col.name}` | {col.kind} | {col.fill:.0%} | {col.empty} |"
            f" {col.unique if not col.unique_capped else f'≥{col.unique}+'} |"
            f" {rng} | {tops} |"
        )
    if prof.ragged:
        lines.append("")
        lines.append(f"⚠️ {prof.ragged} ragged rows.")
    if prof.duplicates:
        lines.append("")
        lines.append(f"⚠️ {prof.duplicates} duplicate rows.")
    return "\n".join(lines)
