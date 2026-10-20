# listam-cli

[![tests](https://github.com/haykarabyan/listam-cli/actions/workflows/tests.yml/badge.svg)](https://github.com/haykarabyan/listam-cli/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A command-line interface for [list.am](https://www.list.am), Armenia's largest classifieds site, built for AI agents.
Search any category, filter car parts by the vehicle they fit, and get listing details, photos and seller phone
numbers as JSON.

> Unofficial and not affiliated with list.am. Intended for personal, low-volume use; respect list.am's terms and
> don't harvest seller contacts in bulk.

## Install

Requires Python ≥ 3.10 and [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/haykarabyan/listam-cli
```

Or run it from a clone with `uv run listam …`.

## Usage

```bash
# Used headlights that fit a 2011–2014 Toyota Camry
listam search "headlight" --make toyota --model camry --generation xv50 --condition used --format text

# Used M5 Pro MacBooks (category 116, processor filter _a138)
listam search -c 116 --brand apple -f "_a138=Apple M5 Pro" --condition used --format text

# One listing: specs, fitment, description, seller, phones, photos saved locally
listam item 23827144 --phone --download ~/Downloads/listam
```

| Command | Purpose |
|---|---|
| `search [QUERY]` | Search listings. Filters: `-c` category, `--make/--model/--generation`, `--brand`, `--condition`, `--location`, `--price-min/--price-max`, `--currency`, `-f KEY=VALUE` |
| `item ID` | Full details; `--phone` adds contacts, `--download DIR` saves all photos |
| `phone ID` | Phone numbers (local and `+374…`), Viber, WhatsApp |
| `images ID` | Download all photos |
| `categories [ID]` | Category tree |
| `filters CATEGORY` | A category's filter params and option ids |
| `makes`, `models MAKE`, `generations MAKE MODEL` | Vehicle lookups for fitment filters |

- Output is JSON (`--format text` for a compact summary). Errors go to stderr as JSON; exit codes are `0` ok,
  `1` error, `2` not found, `3` blocked by Cloudflare.
- Filter values accept names or ids. Category-specific filters (`_aNN`) are listed by `listam filters <category>`.
- Search results are tagged `regular` (real matches), `top` (paid promotion) or `similar` (suggestions).
- `--lang en|hy|ru` switches the UI language. Run `listam <command> --help` for all options.

## Using with AI agents

[`skills/listam/SKILL.md`](skills/listam/SKILL.md) teaches an agent the workflow, part vocabulary in
Armenian/Russian, and category ids. For Claude Code:

```bash
ln -s "$(pwd)/skills/listam" ~/.claude/skills/listam
```

For other agents, copy its contents into your rules or system prompt.

## How it works

list.am has no public API, so the CLI reads the same pages and endpoints the website uses. It passes Cloudflare by
impersonating Chrome with [curl_cffi](https://github.com/lexiforest/curl_cffi), spaces requests about 0.4 s apart,
and caches filter lists in `~/.cache/listam` for 3 days.

Limitations: read-only (no login, messaging or posting), sorting is limited to default/relevance, and parsers may
need updating when list.am changes its HTML.

## Development

```bash
uv run --group dev pytest
```

Tests run offline against saved list.am pages in `tests/fixtures/`, with seller details replaced by placeholders.
Pull requests are welcome, especially parser fixes when list.am changes its layout.

## License

[MIT](LICENSE)
