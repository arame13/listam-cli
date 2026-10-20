# listam-cli

[![tests](https://github.com/haykarabyan/listam-cli/actions/workflows/tests.yml/badge.svg)](https://github.com/haykarabyan/listam-cli/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An agent-friendly command-line interface for [list.am](https://www.list.am), Armenia's largest classifieds site.

Search listings in any category, get full details and **all photos**, and reveal seller **phone numbers**
(plus Viber/WhatsApp links). Everything comes back as JSON, so AI agents (Claude Code, Cursor, custom scripts) can
use list.am directly. It has first-class support for **car spare parts**, with vehicle-fitment filters
(make → model → generation).

> **Unofficial.** Not affiliated with or endorsed by list.am. It reads the public website the way a browser does.
> Use it for personal, low-volume use, respect list.am's terms of service, and don't use it to harvest seller contact
> details in bulk.

## Features

- **Search** any category with keyword, price, location and condition filters, plus every category-specific filter
  (laptop RAM/processor, real-estate seller type, …).
- **Car-part fitment**: `--make toyota --model camry --generation xv70`; names are resolved to list.am ids for you.
- **Listing details**: price with USD/RUB conversion and price history, specs, vehicle compatibility, description,
  seller info and rating.
- **Photos**: full-size image URLs everywhere, and optional download so an agent can actually look at them.
- **Phone numbers** in local and `+374…` E.164 format, plus Viber/WhatsApp links. No login needed.
- **Lookups**: category tree, filter params and option ids, car makes/models/generations.
- Output in English, Armenian or Russian (`--lang en|hy|ru`).
- An [agent skill](skills/listam/SKILL.md) that teaches agents the workflow, part vocabulary and category ids.

## Install

Requires Python ≥ 3.10. The easiest route is [uv](https://docs.astral.sh/uv/):

```bash
# install the `listam` command globally
uv tool install git+https://github.com/haykarabyan/listam-cli

# or run without installing anything permanently
uvx --from git+https://github.com/haykarabyan/listam-cli listam --help

# or work from a clone
git clone https://github.com/haykarabyan/listam-cli
cd listam-cli
uv run listam --help
```

`pipx install git+https://github.com/haykarabyan/listam-cli` works too.

## Quick start

```bash
# Car parts: used headlights that fit a 2011–2014 Toyota Camry
listam search "headlight" --make toyota --model camry --generation xv50 --condition used --format text

# Brake pads (category 1679) for a Kia Sportage under 30,000 AMD
listam search -c 1679 --make kia --model sportage --price-max 30000 --format text

# Used M5 Pro MacBooks (Notebooks = 116, processor filter _a138)
listam search -c 116 --brand apple -f "_a138=Apple M5 Pro" --condition used --sections regular --format text

# Everything about one listing: specs, fitment, description, seller, phones, photos saved locally
listam item 23827144 --phone --download ~/Downloads/listam --format text

listam phone 23827144                      # just the phone numbers
listam images 23827144 --dir ~/Downloads   # just the photos
```

Item arguments accept an id (`23827144`) or any list.am item URL.

## Commands

| Command | What it does |
|---|---|
| `search [QUERY]` | Search listings. Filters: `-c/--category`, `--make`, `--model`, `--generation`, `--brand`, `--condition`, `--location`, `--price-min`, `--price-max`, `--currency amd\|usd`, `--availability sale\|order`, `-f KEY=VALUE` (repeatable). Paging: `--page`, `--pages`, `--limit`. Output: `--sections`, `--sort relevance`, `--format text` |
| `item ID` | Full listing details; `--phone` adds contacts, `--download DIR` saves all photos |
| `phone ID` | Seller phone numbers, Viber and WhatsApp |
| `images ID` | Download every photo (`--dir`, `--size full\|thumb`, `--image-format jpg\|webp`) |
| `categories [ID]` | Top-level categories, or the children of `ID` |
| `filters CATEGORY` | Query params a category accepts, with option ids (`--name P` for one param in full) |
| `makes` / `models MAKE` / `generations MAKE MODEL` | Vehicle lookups for the fitment filters |

Options for every command: `--lang en|hy|ru`, `--pretty` / `--compact` (default: pretty in a terminal, compact
when piped), `--no-cache`. Run `listam <command> --help` for details.

Exit codes: `0` ok, `1` error, `2` not found, `3` blocked by Cloudflare (wait a few minutes and retry).
Errors are printed to stderr as `{"error": "...", "type": "..."}`.

## Filters

Common filters have their own flags. Everything else uses `-f`:

```bash
listam filters 116                  # all params for Notebooks, long option lists truncated
listam filters 116 --name _a25      # every RAM option
listam search -c 116 -f "_a25=32 GB" -f "_a24=16\" - 17.9\"" --condition used
```

- Values can be an option **name** (case-insensitive, unique prefix is fine) or the raw **id**. Ambiguous names
  fail with a list of candidates.
- Category-specific params are named `_aNN` (for example `_a138` processor, `_a25` RAM, `_a139` storage,
  `_a24` screen size in Notebooks).
- `--condition` resolves against the category's own options (`new/used/faulty` for laptops,
  `finished/unfinished` for real estate).
- `--make/--model/--generation` filter by the vehicle a part fits. Without `-c` they search all of
  Parts and Accessories (22).
- Sellers don't always fill in structured fields, so a text query alongside the filters can catch more listings.

Useful car-part category ids: `22` Parts and Accessories, `530` Car Parts, `531` Engine, `532` Body,
`533` Chassis, `535` Brakes, `538` Transmission, `539` Electrical, `540` Lighting, `543` Cooling/Heating,
`115` Wheels and Tires. Run `listam categories 530` for the full list.

## Output

`search` (abridged):

```json
{
  "url": "https://www.list.am/en/category/22?q=headlight&cc_bid=76&cc_mid=1560",
  "total_matches": 3,
  "pages_fetched": 1,
  "has_next_page": true,
  "next_page": 2,
  "results": [
    {
      "id": "23827144",
      "url": "https://www.list.am/en/item/23827144",
      "section": "regular",
      "title": "Toyota Camry 2013 SE դիմացի աջ լուսարձակ",
      "subtitle": "Suitable For Toyota Camry",
      "price": {"amount": 18000, "currency": "AMD", "text": "18,000 ֏"},
      "location": "Erebuni",
      "date": "October 19",
      "photo_count": 4,
      "images": ["https://img.list.am/f/659/98467659.jpg", "..."],
      "thumbnail": "https://img.list.am/r/659/98467659.webp"
    }
  ]
}
```

- `section` is `regular` (real matches, counted in `total_matches`), `top` (paid promotion) or `similar`
  (fuzzy suggestions that list.am adds after the matches). Filter them with `--sections regular`.
- Search cards preview up to about 6 photos. `item` and `images` return the full gallery.
- `has_next_page` can be true even when `total_matches` is small, because later pages hold "similar" ads.

`item` adds `attributes` (condition, part number, RAM, …), `compatibility` (vehicles and generations),
`description`, `description_translation` (list.am machine-translates descriptions on English/Russian pages;
this says from which language), `price_history`, `seller` (name, profile, tenure, rating), `images`, and with
`--phone` a `contact` block:

```json
{
  "phones": [{"display": "(099) 00-00-01", "local": "099000001", "e164": "+37499000001"}],
  "viber": ["viber://chat?number=+37499000001"],
  "whatsapp": ["https://wa.me/37499000001"]
}
```

`--format text` prints a compact human/agent-readable summary instead of JSON for `search` and `item`.

## Using it with AI agents

Any agent that can run shell commands can use `listam`: the output is JSON, the exit codes are documented, and
`--help` is detailed. To give an agent the full workflow (narrow by fitment, check photos, sanity-check listings,
reveal phones only for the shortlist), use the bundled skill:

```bash
# Claude Code: make the skill available in every session
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skills/listam" ~/.claude/skills/listam
```

For other agents (Cursor rules, `AGENTS.md`, system prompts), copy the contents of
[`skills/listam/SKILL.md`](skills/listam/SKILL.md).

## How it works

list.am has no public API. The CLI uses the same endpoints as the website:

| Need | Endpoint |
|---|---|
| Search | `GET /{lang}/category/{id}[/{page}]?q=…&<filters>`; global search is `GET /{lang}/category?q=…&pg=N` |
| Filters | parsed from the category page's sidebar form |
| Car models / generations | `GET /lsw-chain?fecarpartscompat=1&type=m\|g&…` (JSON) |
| Listing | `GET /{lang}/item/{id}` (schema.org microdata; the gallery comes from an inline script) |
| Phones | `GET /rtan?i={id}` (the "Call" popup) |
| Photos | `https://img.list.am/f/{last 3 digits}/{photo id}.jpg` full size, `/r/…` thumbnail |

- **Cloudflare**: list.am rejects ordinary HTTP clients with a JS challenge.
  [curl_cffi](https://github.com/lexiforest/curl_cffi) impersonates Chrome's TLS/HTTP2 fingerprint, so pages load
  without a headless browser.
- **Politeness**: requests are spaced about 0.4 s apart and retried with backoff on 403/429/5xx.
- **Caching**: filter option lists and model/generation chains are cached for 3 days in `~/.cache/listam`
  (or `$XDG_CACHE_HOME/listam`). Use `--no-cache` to refresh.
- **Images**: the image CDN picks JPEG or WebP from the `Accept` header. The CLI asks for the requested format and
  names files by the type it actually receives.

## Limitations

- Read-only. There's no login, so it can't message sellers, save favorites or post ads.
- Sorting is limited to what list.am offers server-side (default or relevance). Sort the JSON yourself for price.
- Filter discovery covers what the category sidebar renders. Some advanced filters may need to be passed by hand
  with `-f`.
- It scrapes HTML. When list.am changes its markup, the parsers in `src/listam/parsers.py` may need updating;
  the fixture tests point to what broke.

## Development

```bash
git clone https://github.com/haykarabyan/listam-cli
cd listam-cli
uv run --group dev pytest        # offline tests against saved pages
uv run listam search "camry" --make toyota --format text   # live smoke test
```

```
src/listam/
  cli.py        argparse commands and output formatting
  client.py     high-level operations: search, item, phone, images, name -> id resolution, cache
  http.py       curl_cffi session (Chrome impersonation), retries, language prefixes, downloads
  parsers.py    pure HTML/JSON -> dict parsers (no network)
skills/listam/SKILL.md   agent skill
tests/                   pytest suite; fixtures/ holds saved list.am pages
```

The fixtures are real list.am pages with seller names, user ids, avatars and phone numbers replaced by
placeholders. Inline SVG and CSS were stripped to keep them small. When adding a fixture, anonymize it the same way.

Issues and pull requests are welcome, especially parser fixes when list.am changes its layout.

## License

[MIT](LICENSE)
