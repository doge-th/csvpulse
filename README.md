# csvpulse 💓

[![CI](https://img.shields.io/github/actions/workflow/status/doge-th/csvpulse/ci.yml?branch=main&label=CI)](https://github.com/doge-th/csvpulse/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)

**Take the pulse of a CSV file in one command.**

Column types, fill rates, uniques, numeric ranges, top values, ragged rows,
duplicate rows, encoding weirdness — no install ceremony, no notebook, no
pandas. One pass over the file, stdlib only.

```
$ csvpulse examples/orders.csv

csvpulse v0.1.0  ·  examples/orders.csv  ·  122 rows · 6 columns · delimiter ',' (sniffed) · UTF-8

Columns
  order_id      [int  ] 100% filled · 119 unique · 1,001…1,120 · mean 1059.78 · top: 1008 (3), ...
  customer      [text ] 100% filled · 8 unique · top: Dmitri (23), Elena (19), 林小满 (17)
  amount        [float] 95% filled · 6 empty · 113 unique · -19.67…798.73 · mean 384.33
  status        [text ] 100% filled · 3 unique · top: paid (80), pending (22), void (19)
  note          [text ] 45% filled · 67 empty · 3 unique · top: refund issued (24), ...
  ordered_on    [text ] 100% filled · 43 unique · top: 2026-10-15 (7), 2026-10-27 (7), ...

Issues
  1 ragged rows (field count ≠ header), first at data row 43
  2 duplicate rows
```

*(real output — [examples/orders.csv](examples/orders.csv) ships with the repo,
messiness included: empty amounts, a ragged row, and duplicates that show up
as `1008 (3)` in the top values.)*

## What you get

- **Column stats** — per column: type guess (`int`/`float`/`text`/`empty`),
  fill rate, empty count, distinct count (with a 10k cap that degrades
  honestly instead of eating RAM), numeric min/max/mean, top-N values.
- **File-level issues** — ragged rows (field count ≠ header, with the first
  offending row number), duplicate rows, lossy decoding warnings.
- **Sniffing** — delimiter via `csv.Sniffer` (`;`/`\t`/`|`/`,`), encoding via
  BOM → strict UTF-8 → latin-1 fallback that tells you it fell back.
- `--json` / `--markdown` output for tickets and pipelines.

## Install

```bash
pip install git+https://github.com/doge-th/csvpulse.git
# or without touching your environment:
pipx install git+https://github.com/doge-th/csvpulse.git
uvx --from git+https://github.com/doge-th/csvpulse.git csvpulse data.csv
```

## Usage

```bash
csvpulse data.csv                     # full report
csvpulse data.csv --delimiter ';'     # override the sniff
csvpulse data.csv --encoding gbk      # override decoding (utf-8 default)
csvpulse data.csv --no-header         # first row is data, not a header
csvpulse data.csv --top 5             # more top values per column
csvpulse data.csv --json | jq '.issues'
csvpulse data.csv --markdown          # paste into the data-quality ticket
```

The JSON document contains everything the table shows — per-column stats
(`kind`, `fill`, `empty`, `unique`, ranges, `top`), plus `ragged`,
`ragged_lines` and `duplicates` at the file level.

## Method (and its honest limits)

- **Type guess**: a column is `int`/`float` only when *every* non-empty value
  parses as one — otherwise it's `text`. No date inference yet; dates show as
  text with their most frequent values visible, which is usually enough to
  spot the format.
- **Distinct counting** stops at 10,000 values per column and reports
  `unique_capped` instead of ballooning memory. Top values stop being
  representative at that point too — the flag tells you.
- **Duplicate scan** hashes rows and skips past 1,000,000 rows (reported,
  not silent).
- **Ragged rows** are excluded from per-column stats but still counted as
  rows — they're the file's problem, not the column's.
- Honors [`NO_COLOR`](https://no-color.org/); plain output when piped.

## 中文说明

**csvpulse:一条命令给 CSV 做体检。** 列类型推断、填充率、唯一值、数值区间、
最高频值、错位行、重复行、编码 sniff(BOM → UTF-8 → latin-1 兜底并如实
报告)——不装 pandas、不开 notebook,标准库单趟扫完。

```bash
pip install git+https://github.com/doge-th/csvpulse.git
csvpulse data.csv                    # 全身体检
csvpulse data.csv --delimiter ';'    # 分隔符不对时手动指定
csvpulse data.csv --markdown         # 贴进数据质量工单
```

类型推断的口径很诚实:整列**所有**非空值都能解析成数字才算 int/float,否则
就是 text;唯一值数到 1 万封顶,如实标注 `unique_capped` 而不是悄悄吃内存。
错位行计入行数但不计入列统计——那是文件的问题,不是列的。

配套工具:[toktree](https://github.com/doge-th/toktree)、
[githotspot](https://github.com/doge-th/githotspot)、
[todomold](https://github.com/doge-th/todomold)、
[awakehours](https://github.com/doge-th/awakehours)、
[pyverscan](https://github.com/doge-th/pyverscan)。

## Development

```bash
python -m unittest discover -s tests   # zero-dep suite
```

## License

[MIT](LICENSE) © 2026 doge-th
