"""High-level list.am operations: search, item details, phones, images, lookups."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from . import parsers
from .http import Http, ListamError, NotFound

PARTS_CATEGORY = 22  # "Parts and Accessories" - where car-compatibility filters live
CACHE_TTL = 3 * 24 * 3600
# Bump when parser output changes so stale cached filter lists are not reused.
CACHE_VERSION = 3


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "listam"


def item_id_from(value: str | int) -> str:
    """Accept '22973564', 'https://www.list.am/en/item/22973564?x=1', etc."""
    s = str(value).strip()
    m = re.search(r"/item/(\d+)", s) or re.fullmatch(r"(\d+)", s)
    if not m:
        raise ListamError(f"not a list.am item id or URL: {value!r}")
    return m.group(1)


class AmbiguousName(ListamError):
    pass


def resolve_option(options: list[dict[str, Any]], value: str, what: str) -> str:
    """Map a human name ('toyota', 'Arabkir') or raw id ('76') to an option value."""
    v = str(value).strip()
    if any(o["value"] == v for o in options):
        return v
    if not options:  # free-text param, or nothing to resolve against
        return v
    low = v.lower()

    def base(name: str) -> str:  # "XV70 (2017 - 2021)" -> "xv70"
        return re.sub(r"\s*\(.*?\)\s*$", "", name).strip().lower()

    for test in (
        lambda o: o["name"].lower() == low,
        lambda o: base(o["name"]) == low,
        lambda o: o["name"].lower().startswith(low),
        lambda o: low in o["name"].lower(),
    ):
        hits = list({o["value"]: o for o in options if test(o)}.values())
        if len(hits) == 1:
            return hits[0]["value"]
        if len(hits) > 1:
            exact_group = [o for o in hits if o.get("is_group")]
            if len(exact_group) == 1:
                return exact_group[0]["value"]
            names = ", ".join(f"{o['name']} ({o['value']})" for o in hits[:12])
            raise AmbiguousName(f"{what} {value!r} is ambiguous: {names}")
    if v.isdigit():
        return v
    raise ListamError(f"unknown {what} {value!r}; use `listam filters` / `listam makes` to see valid values")


class Listam:
    def __init__(self, lang: str = "en", use_cache: bool = True):
        self.http = Http(lang=lang)
        self.lang = lang
        self.use_cache = use_cache
        # Filter option ids are language-independent; names are resolved in English.
        self._en = self.http if lang == "en" else Http(lang="en")

    # ------------------------------------------------------------------ cache

    def _cached(self, key: str, fetch) -> Any:
        path = cache_dir() / f"v{CACHE_VERSION}-{key}.json"
        if self.use_cache and path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL:
            try:
                return json.loads(path.read_text())
            except ValueError:
                pass
        data = fetch()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False))
        except OSError:
            pass
        return data

    # ------------------------------------------------------------------ lookups

    @staticmethod
    def _category_page(http: Http, category: int | None, path: str, params: dict[str, Any] | None = None):
        """GET a category page; list.am redirects unknown categories to the home page."""
        resp = http.get(http.page_url(path), params=params)
        if category and "/category" not in str(resp.url):
            raise NotFound(f"category {category} does not exist (see `listam categories`)")
        return resp

    def filters(self, category: int, lang: str | None = None) -> dict[str, Any]:
        lang = lang or self.lang
        http = self._en if lang == "en" else self.http

        def fetch():
            return parsers.parse_filters(self._category_page(http, category, f"/category/{category}").text)

        return self._cached(f"filters-{lang}-{category}", fetch)

    def categories(self, parent: int | None = None) -> list[dict[str, Any]]:
        if parent is None:
            html = self.http.get_html(self.http.page_url("/"))
            return parsers.parse_top_categories(html)
        nodes = parsers.parse_categories(self._category_page(self.http, parent, f"/category/{parent}").text)
        # The sidebar shows ancestors, the selected node, then its children.
        idx = next((i for i, n in enumerate(nodes) if n["selected"]), None)
        children = [n for n in nodes if n["id"] != parent] if idx is None else nodes[idx + 1 :]
        return [{"id": n["id"], "name": n["name"]} for n in children]

    def is_vehicle_category(self, category: int | None) -> bool:
        """Vehicle listings (cars, trucks…) filter on bid/mid; parts filter on cc_bid/cc_mid."""
        if not category or category == PARTS_CATEGORY:
            return False
        f = self.filters(category, lang="en")
        return "mid" in f and "cc_bid" not in f

    def _make_param(self, category: int) -> str:
        return "bid" if self.is_vehicle_category(category) else "cc_bid"

    def makes(self, category: int = PARTS_CATEGORY) -> list[dict[str, Any]]:
        opts = self.filters(category).get(self._make_param(category), {}).get("options", [])
        return [{"id": int(o["value"]), "name": o["name"]} for o in opts]

    def _chain(self, kind: str, category: int, make_id: str, model_id: str | None = None) -> dict[str, Any]:
        if kind == "m" and self.is_vehicle_category(category):
            params = dict(cname="make", makes=make_id, c=category, existingOnly=1)
            data = self._cached(f"chain-vm-{category}-{make_id}", lambda: self._en.get_json("/lsw-chain", params=params))
            return parsers.parse_chain(data, "_idmodel")
        if kind == "g" and self.is_vehicle_category(category):
            raise ListamError("generations are only available for car parts (vehicle listings filter by year instead, e.g. -f _a2_1=2018)")
        if kind == "m":
            params = dict(fecarpartscompat=1, type="m", nextid="cc_mid", cid="cc_bid", cc_bid=make_id, c=category, flat=0, keep_ids="")
            key = "cc_mid"
        else:
            params = dict(fecarpartscompat=1, type="g", nextid="cc_gid", cid="cc_mid", cc_mid=model_id, cc_bid=make_id, c=category, flat=0, keep_ids="")
            key = "cc_gid"
        cache_key = f"chain-{kind}-{make_id}-{model_id or ''}"
        data = self._cached(cache_key, lambda: self._en.get_json("/lsw-chain", params=params))
        return parsers.parse_chain(data, key)

    def resolve_make(self, make: str, category: int = PARTS_CATEGORY) -> str:
        opts = self.filters(category, lang="en").get(self._make_param(category), {}).get("options", [])
        return resolve_option(opts, make, "make")

    def models(self, make: str, category: int = PARTS_CATEGORY) -> dict[str, Any]:
        make_id = self.resolve_make(make, category)
        return self._chain("m", category, make_id)

    def resolve_model(self, make_id: str, model: str, category: int = PARTS_CATEGORY) -> str:
        items = self._chain("m", category, make_id)["items"]
        return resolve_option([{"value": str(i["id"]), "name": i["name"]} for i in items], model, "model")

    def generations(self, make: str, model: str, category: int = PARTS_CATEGORY) -> dict[str, Any]:
        make_id = self.resolve_make(make, category)
        model_id = self.resolve_model(make_id, model, category)
        return self._chain("g", category, make_id, model_id)

    def resolve_generation(self, make_id: str, model_id: str, gen: str, category: int = PARTS_CATEGORY) -> str:
        items = self._chain("g", category, make_id, model_id)["items"]
        return resolve_option([{"value": str(i["id"]), "name": i["name"]} for i in items], gen, "generation")

    def resolve_filter(self, category: int | None, name: str, value: str) -> str:
        if category is None:
            category = PARTS_CATEGORY if name in ("cc_bid", "bid", "cnd", "type") else 0
        opts = self.filters(category, lang="en").get(name, {}).get("options", []) if category else []
        return resolve_option(opts, value, name)

    # ------------------------------------------------------------------ search

    def search(
        self,
        query: str | None = None,
        category: int | None = None,
        *,
        make: str | None = None,
        model: str | None = None,
        generation: str | None = None,
        brand: str | None = None,
        condition: str | None = None,
        location: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        currency: str | None = None,
        availability: str | None = None,
        relevance: bool = False,
        extra: dict[str, str] | None = None,
        page: int = 1,
        pages: int = 1,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if query:
            params["q"] = query
        if make or model or generation:
            category = category or PARTS_CATEGORY
            if not make:
                raise ListamError("--model/--generation require --make")
            if generation and not model:
                raise ListamError("--generation requires --model")
            # Vehicle categories filter on the car itself (bid/mid); elsewhere --make
            # means "part fits this vehicle" and uses the parts compatibility filters.
            vehicle = self.is_vehicle_category(category)
            fcat = category if vehicle else PARTS_CATEGORY
            make_id = self.resolve_make(make, fcat)
            params["bid" if vehicle else "cc_bid"] = make_id
            if model:
                model_id = self.resolve_model(make_id, model, fcat)
                params["mid" if vehicle else "cc_mid"] = model_id
                if generation:
                    params["cc_gid"] = self.resolve_generation(make_id, model_id, generation, fcat)
        filter_cat = category
        if brand:
            params["bid"] = self.resolve_filter(filter_cat or PARTS_CATEGORY, "bid", brand)
        if condition:
            cnd_opts = self.filters(filter_cat, lang="en").get("cnd", {}).get("options", []) if filter_cat else []
            if cnd_opts:  # meaning differs per category (e.g. real estate: Finished/Unfinished)
                params["cnd"] = resolve_option(cnd_opts, condition, "condition")
            else:
                params["cnd"] = {"new": "1", "used": "2"}.get(condition.lower()) or resolve_option([], condition, "condition")
        if location:
            params["n"] = self.resolve_filter(filter_cat or PARTS_CATEGORY, "n", location)
        if availability:
            amap = {"sale": "1", "for-sale": "1", "order": "6", "to-order": "6"}
            params["type"] = amap.get(availability.lower(), availability)
        if currency:
            params["crc"] = {"amd": "0", "usd": "1"}.get(currency.lower(), currency)
        if price_min is not None:
            params["price1"] = price_min
        if price_max is not None:
            params["price2"] = price_max
        if relevance:
            params["srt"] = 4
        for k, v in (extra or {}).items():
            params[k] = self.resolve_filter(filter_cat, k, v) if filter_cat else v

        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        total = None
        has_next = False
        urls = []
        for p in range(page, page + max(1, pages)):
            if category:
                path = f"/category/{category}" + (f"/{p}" if p > 1 else "")
                pp = dict(params)
            else:
                path = "/category"
                pp = dict(params, **({"pg": p} if p > 1 else {}))
            resp = self._category_page(self.http, category, path, pp)
            urls.append(str(resp.url))
            parsed = parsers.parse_search(resp.text)
            if total is None:
                total = parsed["total"]
            for r in parsed["results"]:
                if r["id"] not in seen:
                    seen.add(r["id"])
                    results.append(r)
            has_next = parsed["has_next_page"]
            if not has_next:
                break
        return {
            "url": urls[0],
            "params": params,
            "category": category,
            "total_matches": total,
            "pages_fetched": len(urls),
            "has_next_page": has_next,
            "next_page": page + len(urls) if has_next else None,
            "results": results,
        }

    # ------------------------------------------------------------------ items

    def item(self, item: str | int) -> dict[str, Any]:
        iid = item_id_from(item)
        html = self.http.get_html(self.http.page_url(f"/item/{iid}"))
        known: set[str] = set()
        cat = parsers.item_category_id(html)
        if cat:
            try:  # filter labels tell attribute names from values; best effort
                known = {v["label"] for v in self.filters(cat).values() if v.get("label")}
            except ListamError:
                pass
        try:
            return parsers.parse_item(html, iid, known_labels=known)
        except ValueError as e:
            raise NotFound(f"item {iid}: {e}") from None

    def phone(self, item: str | int) -> dict[str, Any]:
        iid = item_id_from(item)
        html = self.http.get_html(
            "/rtan",
            params={"i": iid, "_rtt": 1},
            headers={"Referer": self.http.page_url(f"/item/{iid}"), "X-Requested-With": "XMLHttpRequest"},
        )
        data = parsers.parse_phone(html, iid)
        if not data["phones"]:
            data["note"] = "no phone numbers shown for this listing (seller may only accept messages, or ad is inactive)"
        return data

    def download_images(
        self, urls: list[str], dest: Path, ext: str = "jpg", size: str = "full"
    ) -> list[str]:
        paths = []
        for i, url in enumerate(urls, 1):
            image_id = url.rsplit("/", 1)[-1].split(".")[0]
            url = parsers.image_url(image_id, size=size, ext=ext if size == "full" else "webp")
            target = dest / f"{i:02d}_{image_id}.{url.rsplit('.', 1)[-1]}"
            existing = sorted(dest.glob(f"{i:02d}_{image_id}.*")) if dest.exists() else []
            target = existing[0] if existing else self.http.download(url, target)
            paths.append(str(target.resolve()))
        return paths
