# Download pictures before the call, so the picture pop-ups never wait on the network. Both ways: Indian things she
# mentions (for the grandkid) and American things the grandkid mentions (for her, --two-way). Fills the same cache the
# call uses (images/cache/cache.json + images/cache/<name>.jpg, gitignored), from Wikipedia categories (Indian foods,
# festivals, clothing, music, dances, games, temples, places; American foods, holidays, school, sports) and from
# lexicon.json words that have no picture in the library. Anything else she mentions is looked up in the background during the
# call (pictures.py) and cached, so it's instant the next time.
#   python tools/prefetch_pictures.py            # everything below (~15 minutes, ~250 MB the first time; run again to fill gaps)
#   python tools/prefetch_pictures.py --refresh  # fetch again what's already cached
# Word-list words come first, then Telugu-specific categories, then broader Indian ones. Wikipedia rate-limits
# (HTTP 429), so requests are paced and retried; anything still missed is fetched by the next run.
# Pictures and descriptions are Wikipedia page summaries (free to reuse with credit; the credit link is kept).
import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pictures import CACHE_DIR, HEADERS  # noqa: E402

API = "https://en.wikipedia.org/w/api.php"
# (category, how many levels of subcategories to follow), most likely to come up first. Subcategories only where
# they stay on topic: "Hindu festivals" -> subcategories wandered into Nepal, Kerala temple fairs and college fests.
CATEGORIES = [
    ("Andhra cuisine", 1), ("Telangana cuisine", 1), ("Festivals in Andhra Pradesh", 1), ("Festivals in Telangana", 1),
    ("Hindu temples in Andhra Pradesh", 1), ("Hindu temples in Telangana", 1), ("Tourist attractions in Andhra Pradesh", 1),
    ("Rivers of Andhra Pradesh", 0), ("Cities and towns in Andhra Pradesh", 0),
    ("South Indian cuisine", 0), ("Indian desserts", 0), ("Indian snack foods", 0), ("Indian breads", 0),
    ("Indian condiments", 0), ("Indian drinks", 0), ("Indian rice dishes", 0), ("Indian curries", 0), ("Indian spices", 0),
    ("Indian cuisine", 0), ("Hindu festivals", 0), ("Festivals in India", 0), ("Hindu deities", 0), ("Indian clothing", 0),
    ("Indian musical instruments", 0), ("Carnatic music", 0), ("Dances of India", 0), ("Indian games", 0),
    ("Fruits originating in Asia", 0),
]
# American things a grandkid talks about that a grandmother in India may never have seen
AMERICAN = [
    ("American cuisine", 0), ("American desserts", 0), ("American breakfast foods", 0), ("American sandwiches", 0),
    ("American snack foods", 0), ("American drinks", 0), ("Tex-Mex cuisine", 0), ("Fast food", 0), ("Pies", 0),
    ("Barbecue", 0), ("Cuisine of the Southern United States", 0), ("Public holidays in the United States", 0), ("Thanksgiving", 0), ("Halloween", 0),
    ("School dances", 0), ("Secondary education in the United States", 0), ("American football", 0), ("Baseball", 0),
    ("Basketball", 0), ("Winter sports", 0),
]
SKIP_TITLE = re.compile(r"^(List of|Lists of|Outline of|Index of|History of)|disambiguation", re.IGNORECASE)


def get(url, **kw):
    """GET with Wikipedia's rate limit respected: paced, and on 429 wait (Retry-After, else 5, 10, 20 s) and retry."""
    for attempt in range(5):
        time.sleep(0.2)
        r = requests.get(url, headers=HEADERS, timeout=20, **kw)
        if r.status_code != 429:
            r.raise_for_status()
            return r
        wait = r.headers.get("Retry-After", "")
        time.sleep(int(wait) if wait.isdigit() else 5 * 2 ** attempt)
    r.raise_for_status()


def api(**params):
    return get(API, params={"action": "query", "format": "json", **params}).json()


def members(category, kind):
    out, cont = [], {}
    while True:
        data = api(list="categorymembers", cmtitle="Category:" + category, cmtype=kind, cmlimit="max",
                   **({"cmnamespace": 0} if kind == "page" else {}), **cont)
        out += [m["title"] for m in data["query"]["categorymembers"]]
        if "continue" not in data:
            return out
        cont = data["continue"]


def titles_from_categories(categories):
    titles, seen = [], set()
    todo = list(categories)
    while todo:
        cat, depth = todo.pop(0)
        if cat in seen:
            continue
        seen.add(cat)
        try:
            titles += members(cat, "page")
            if depth > 0:
                todo += [(sub.split(":", 1)[1], depth - 1) for sub in members(cat, "subcat")]
        except requests.RequestException as e:
            print(f"  (skipped {cat}: {type(e).__name__})")
    return titles


def titles_from_lexicon():
    """Word-list words without a library picture: their English name, as the translator would say it."""
    lexicon = json.load(open(os.path.join(ROOT, "lexicon.json"), encoding="utf-8"))
    library = json.load(open(os.path.join(ROOT, "images", "library.json"), encoding="utf-8"))["items"]
    pictured = {lid for it in library.values() for lid in it.get("lexicon_ids", [])}
    out = []
    for e in lexicon.get("te", []):
        if e["id"] in pictured or e.get("category") not in ("food", "festival", "place", "clothing", "vehicle", "culture"):
            continue
        out += [n for n in {e.get("roman"), e.get("translate_as")} if n]
    return out


def summaries(titles):
    """{title: page} with a thumbnail, a one-sentence description and every redirect to it, 20 titles per request."""
    pages = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        try:
            data = api(titles="|".join(batch), redirects=1, prop="pageimages|extracts|redirects|info", inprop="url",
                       pithumbsize=400, exintro=1, explaintext=1, exsentences=1, exlimit="max", rdlimit="max")
        except requests.RequestException as e:
            print(f"\n  (skipped 20 pages: {type(e).__name__}; the next run tries them again)")
            continue
        for page in data["query"].get("pages", {}).values():
            if "missing" not in page and page.get("thumbnail") and not SKIP_TITLE.search(page["title"]):
                pages[page["title"]] = page
        print(f"\r  {min(i + 20, len(titles))}/{len(titles)} pages looked up, {len(pages)} with pictures", end="", flush=True)
    print()
    return pages


def key(title):
    """The cache key the call looks up: the lowercase name without Wikipedia's "(food)" / "(festival)"."""
    return re.sub(r"\s*\(.*?\)\s*", " ", title).strip().lower()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true", help="fetch again what's already cached")
    args = p.parse_args()

    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, "cache.json")
    cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}

    print("Listing pages...")
    indian = list(dict.fromkeys(titles_from_lexicon() + titles_from_categories(CATEGORIES)))
    american = [t for t in dict.fromkeys(titles_from_categories(AMERICAN)) if t not in set(indian)]
    region = {**{t: "in" for t in indian}, **{t: "us" for t in american}}
    titles = [t for t in indian + american if args.refresh or not cache.get(key(t))]
    print(f"{len(titles)} to look up ({sum(region[t] == 'us' for t in titles)} American)")
    pages = summaries(titles)
    by_page = {}  # a redirect resolves to the page's title; its region is the one it was listed under
    for page in pages.values():
        listed = [region.get(page["title"])] + [region.get(r["title"]) for r in page.get("redirects", [])]
        by_page[page["title"]] = next((r for r in listed if r), "in")

    lock, done = threading.Lock(), [0]

    def download(page):
        slug = re.sub(r"[^a-z0-9]+", "_", key(page["title"])).strip("_")
        path = os.path.join(CACHE_DIR, slug + ".jpg")
        if args.refresh or not os.path.exists(path):
            try:
                r = get(page["thumbnail"]["source"])
                with open(path, "wb") as f:
                    f.write(r.content)
            except requests.RequestException:
                return
        first = re.match(r"(.+?[.!?])(\s|$)", page.get("extract", "") or "")
        entry = {"name": key(page["title"]).title(), "description": first.group(1) if first else "",
                 "image": f"images/cache/{slug}.jpg", "category": "web", "credit": page.get("fullurl", ""),
                 # from our categories or word list, so no need to ask Laya during the call what it is
                 "indian": by_page[page["title"]] == "in", "american": by_page[page["title"]] == "us"}
        with lock:
            for name in [page["title"]] + [r["title"] for r in page.get("redirects", [])]:
                if args.refresh or not cache.get(key(name)):
                    cache[key(name)] = entry
            done[0] += 1
            if done[0] % 50 == 0:
                print(f"\r  {done[0]}/{len(pages)} pictures saved", end="", flush=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(download, pages.values()))
    tmp = cache_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1, ensure_ascii=False)
    os.replace(tmp, cache_path)
    print(f"\nDone: {done[0]} pictures; the cache now knows {sum(1 for v in cache.values() if v)} names "
          f"({len(os.listdir(CACHE_DIR))} files in {os.path.relpath(CACHE_DIR, ROOT)}/).")


if __name__ == "__main__":
    main()
