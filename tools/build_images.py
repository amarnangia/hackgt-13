# Build the picture library: images/<id>.jpg plus images/library.json (name, description, aliases, credit).
# Pictures and one-line descriptions come from Wikipedia's page summaries (free to reuse with credit, no API key).
#   python tools/build_images.py            # fetch anything missing
#   python tools/build_images.py --refresh  # fetch everything again
# Add an item: (id, Wikipedia title, category, [English words that mean it], [lexicon.json ids]).
# Don't use everyday English words as aliases: "well" popped up a water well for "are you doing well?".
import json
import os
import re
import sys
import time
import urllib.parse

import requests

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")
HEADERS = {"User-Agent": "hackgt-call-translator/0.1 (https://github.com/amarnangia/hackgt-13)"}

ITEMS = [
    # --- Indian food ---
    ("pulihora", "Pulihora", "food", ["tamarind rice", "pulihora"], ["pulihora"]),
    ("pesarattu", "Pesarattu", "food", ["pesarattu", "green gram dosa", "moong dal dosa"], ["pesarattu"]),
    ("dosa", "Dosa (food)", "food", ["dosa", "dosas"], ["dosa"]),
    ("idli", "Idli", "food", ["idli", "idlis"], ["idli"]),
    ("upma", "Upma", "food", ["upma"], ["upma"]),
    ("dal", "Dal", "food", ["dal", "daal", "lentils", "dal rice"], ["pappu"]),
    ("sambar", "Sambar (dish)", "food", ["sambar"], ["sambar"]),
    ("rasam", "Rasam", "food", ["rasam"], ["rasam"]),
    ("curd_rice", "Curd rice", "food", ["curd rice", "yogurt rice"], ["perugu_annam"]),
    ("avakaya", "Avakaya", "food", ["mango pickle", "avakaya"], ["avakaya"]),
    ("gongura", "Gongura", "food", ["gongura", "sorrel leaves", "sorrel"], ["gongura"]),
    ("biryani", "Hyderabadi biryani", "food", ["biryani"], ["biryani"]),
    ("laddu", "Laddu", "food", ["laddu", "laddus", "ladoo", "ladoos"], ["laddu"]),
    ("ariselu", "Ariselu", "food", ["ariselu", "rice sweets"], ["ariselu"]),
    ("bobbatlu", "Puran poli", "food", ["bobbatlu", "sweet flatbread", "puran poli"], ["bobbatlu"]),
    ("chapati", "Chapati", "food", ["chapati", "chapatis", "roti", "rotis"], ["chapati"]),
    ("payasam", "Kheer", "food", ["payasam", "kheer", "rice pudding"], ["payasam"]),
    ("murukku", "Murukku", "food", ["murukku", "jantikalu", "chakli"], ["jantikalu"]),
    ("pongal_dish", "Pongal (dish)", "food", ["pongal"], []),
    ("poornalu", "Poornalu", "food", ["boorelu", "poornalu", "purnalu"], ["boorelu"]),
    ("pootharekulu", "Pootharekulu", "food", ["pootharekulu", "paper sweet"], []),
    ("kakinada_kaja", "Kakinada Kaja", "food", ["kaja", "kakinada kaja"], []),
    ("sakinalu", "Sakinalu", "food", ["sakinalu"], []),
    ("bonda", "Bonda (snack)", "food", ["bonda", "bondas"], []),
    ("vada", "Medu vada", "food", ["vada", "vadas", "vadai", "garelu"], []),
    ("pani_puri", "Panipuri", "food", ["pani puri", "panipuri", "golgappa"], []),
    ("samosa", "Samosa", "food", ["samosa", "samosas"], []),
    ("jalebi", "Jalebi", "food", ["jalebi", "jalebis"], []),
    ("gulab_jamun", "Gulab jamun", "food", ["gulab jamun"], []),
    ("paneer", "Paneer", "food", ["paneer"], []),
    ("paneer_curry", "Palak paneer", "food", ["paneer curry", "palak paneer"], []),
    ("chole", "Chole bhature", "food", ["chole", "chole bhature", "chickpea curry"], []),
    ("paratha", "Paratha", "food", ["paratha", "parathas"], []),
    ("naan", "Naan", "food", ["naan"], []),
    ("indian_pickle", "South Asian pickle", "food", ["pickle", "pickles"], []),
    ("chutney", "Chutney", "food", ["chutney", "chutneys"], ["pachadi"]),
    ("papadum", "Papadam", "food", ["papad", "papadum", "appadam"], []),
    ("halwa", "Gajar ka halwa", "food", ["halwa", "carrot halwa", "gajar halwa"], []),
    ("mysore_pak", "Mysore pak", "food", ["mysore pak"], []),
    ("kaju_katli", "Kaju katli", "food", ["kaju katli", "kaju barfi"], []),
    ("lassi", "Lassi", "food", ["lassi"], []),
    ("chai", "Masala chai", "food", ["chai", "masala chai", "tea"], []),
    ("filter_coffee", "Indian filter coffee", "food", ["filter coffee"], []),
    ("coconut_water", "Coconut water", "food", ["tender coconut", "coconut water"], ["kobbari"]),
    ("jaggery", "Jaggery", "food", ["jaggery"], ["bellam"]),
    ("ghee", "Ghee", "food", ["ghee"], ["neyyi"]),
    ("mango", "Mango", "food", ["mango", "mangoes", "raw mango"], ["mamidi"]),
    ("banana", "Banana", "food", ["banana", "bananas"], ["arati"]),
    ("jackfruit", "Jackfruit", "food", ["jackfruit"], []),
    ("guava", "Guava", "food", ["guava", "guavas"], []),
    ("sugarcane", "Sugarcane juice", "food", ["sugarcane", "sugarcane juice"], []),
    ("pav_bhaji", "Pav bhaji", "food", ["pav bhaji"], []),
    ("uttapam", "Uttapam", "food", ["uttapam", "uthappam"], []),
    ("poha", "Poha (rice)", "food", ["poha", "atukulu"], []),
    ("pakora", "Pakora", "food", ["pakora", "pakoras", "bajji", "bajjis", "mirchi bajji"], []),
    ("kulfi", "Kulfi", "food", ["kulfi"], []),
    ("prasadam", "Prasada", "food", ["prasadam", "prasad"], ["prasadam"]),
    ("pulao", "Pilaf", "food", ["pulao", "pulav"], []),
    ("tamarind", "Tamarind", "food", ["tamarind"], []),
    ("curry_leaves", "Curry tree", "food", ["curry leaves"], []),
    ("ragi", "Finger millet", "food", ["ragi", "finger millet", "ragi java"], []),
    ("thali", "Thali", "food", ["thali", "banana leaf meal", "full meal"], ["bhojanam"]),
    ("rice", "Cooked rice", "food", ["rice", "cooked rice"], ["annam"]),
    ("curry", "Curry", "food", ["curry", "curries"], ["kura"]),
    # --- vehicles ---
    ("auto", "Auto rickshaw", "vehicle", ["auto-rickshaw", "auto rickshaw", "auto"], ["auto"]),
    ("rickshaw", "Cycle rickshaw", "vehicle", ["rickshaw", "cycle rickshaw"], ["rickshaw"]),
    ("bullock_cart", "Bullock cart", "vehicle", ["bullock cart", "bullock carts"], []),
    ("indian_train", "Rail transport in India", "vehicle", ["train"], ["railu"]),
    ("scooter", "Motor scooter", "vehicle", ["scooter", "scooty"], []),
    # --- places, nature, animals ---
    ("temple", "Thousand Pillar Temple", "place", ["temple", "temples"], ["temple"]),
    ("gopuram", "Gopuram", "place", ["gopuram", "temple tower"], []),
    ("paddy_field", "Paddy field", "place", ["farm field", "paddy field", "rice field"], ["polam"]),
    ("village_market", "Haat bazaar", "place", ["weekly village market", "village market", "market", "bazaar"], ["santa"]),
    ("well", "Water well", "place", ["village well", "water well"], []),
    ("tulsi", "Ocimum tenuiflorum", "place", ["tulsi", "holy basil", "tulasi"], []),
    ("banyan", "Banyan", "place", ["banyan tree", "banyan"], []),
    ("neem", "Azadirachta indica", "place", ["neem", "neem tree"], []),
    ("coconut_tree", "Coconut", "place", ["coconut tree", "coconut", "coconuts"], []),
    ("cow", "Zebu", "place", ["cow", "cows"], ["aavu"]),
    ("buffalo", "Water buffalo", "place", ["buffalo", "buffaloes"], []),
    ("peacock", "Indian peafowl", "place", ["peacock", "peacocks"], []),
    ("monsoon", "Monsoon", "place", ["monsoon", "rains"], ["vana"]),
    ("charminar", "Charminar", "place", ["charminar"], []),
    ("tirupati", "Venkateswara Temple, Tirumala", "place", ["tirupati", "tirumala"], []),
    # --- clothing and jewelry ---
    ("saree", "Sari", "clothing", ["saree", "sari", "sarees", "saris"], ["saree"]),
    ("silk_saree", "Kanchipuram silk sari", "clothing", ["silk saree", "silk sari", "pattu saree"], ["pattu_cheera"]),
    ("dhoti", "Veshti", "clothing", ["dhoti", "pancha", "veshti"], ["pancha"]),
    ("half_saree", "Half saree", "clothing", ["half-saree", "half saree", "langa voni"], ["langa_voni"]),
    ("kurta", "Kurta", "clothing", ["kurta", "kurtas"], []),
    ("lungi", "Lungi", "clothing", ["lungi"], []),
    ("bangles", "Bangle", "clothing", ["bangles", "bangle"], ["gajulu"]),
    ("bindi", "Bindi", "clothing", ["bindi", "bottu"], ["bottu"]),
    ("mangalsutra", "Mangalsutra", "clothing", ["mangalsutra", "thali chain"], []),
    ("anklet", "Anklet", "clothing", ["anklets", "anklet", "payal"], []),
    ("jhumka", "Jhumka", "clothing", ["jhumkas", "jhumka", "earrings"], []),
    ("mehndi", "Mehndi", "clothing", ["mehndi", "henna"], []),
    # --- festivals and culture ---
    ("sankranti", "Makar Sankranti", "festival", ["sankranti", "makar sankranti"], ["sankranti"]),
    ("ugadi", "Ugadi", "festival", ["ugadi"], ["ugadi"]),
    ("diwali", "Diwali", "festival", ["diwali", "deepavali"], ["diwali"]),
    ("ganesh_chaturthi", "Ganesh Chaturthi", "festival", ["vinayaka chavithi", "ganesh chaturthi", "ganesha"], ["vinayaka_chavithi"]),
    ("bathukamma", "Bathukamma", "festival", ["bathukamma"], ["bathukamma"]),
    ("holi", "Holi", "festival", ["holi"], []),
    ("dussehra", "Vijayadashami", "festival", ["dussehra", "dasara", "vijayadashami"], []),
    ("pongal_festival", "Thai Pongal", "festival", ["pongal festival"], []),
    ("kite", "Kite", "festival", ["kites", "kite"], ["galipatam"]),
    ("diya", "Diya (lamp)", "festival", ["diya", "diyas", "oil lamp", "oil lamps"], []),
    ("puja", "Puja (Hinduism)", "festival", ["puja", "pooja"], ["puja"]),
    ("aarti", "Arti (Hinduism)", "festival", ["aarti", "harathi"], []),
    ("wedding", "Hindu wedding", "festival", ["wedding", "marriage"], ["pelli"]),
    ("rangoli", "Kolam", "festival", ["rangoli", "muggu", "muggulu", "kolam"], ["muggu"]),
    ("golu", "Bommai Kolu", "festival", ["bommala koluvu", "golu", "doll festival"], []),
    ("veena", "Saraswati veena", "festival", ["veena"], []),
    ("kuchipudi", "Kuchipudi", "festival", ["kuchipudi", "classical dance"], []),
    ("bharatanatyam", "Bharatanatyam", "festival", ["bharatanatyam"], []),
    ("carnatic", "Carnatic music", "festival", ["carnatic music", "carnatic"], []),
    ("cricket", "Cricket", "festival", ["cricket"], []),
    # --- household ---
    ("pressure_cooker", "Pressure cooking", "place", ["pressure cooker"], []),
    ("tawa", "Tava", "place", ["tawa", "tava", "griddle"], []),
    ("steel_tumbler", "Dabarah", "place", ["tumbler", "davara"], []),
    ("mortar_pestle", "Mortar and pestle", "place", ["mortar and pestle", "grinding stone", "rolu"], []),
    ("charpoy", "Charpai", "place", ["charpoy", "rope cot"], []),
    ("jhoola", "Swing (seat)", "place", ["jhoola", "uyyala", "swing seat"], []),
    ("rangoli_powder", "Rangoli", "festival", ["rangoli powder"], []),
    # --- American things (so relatives can see what the kid's life is like) ---
    ("thanksgiving", "Thanksgiving (United States)", "festival", ["thanksgiving"], []),
    ("halloween", "Halloween", "festival", ["halloween", "trick-or-treating", "trick or treating"], []),
    ("christmas_tree", "Christmas tree", "festival", ["christmas tree", "christmas"], []),
    ("fourth_of_july", "Independence Day (United States)", "festival", ["fourth of july", "4th of july", "independence day"], []),
    ("hamburger", "Hamburger", "food", ["hamburger", "burger", "burgers"], []),
    ("pizza", "Pizza", "food", ["pizza", "pizzas"], []),
    ("hot_dog", "Hot dog", "food", ["hot dog", "hot dogs"], []),
    ("mac_and_cheese", "Macaroni and cheese", "food", ["mac and cheese", "macaroni and cheese"], []),
    ("pancake", "Pancake", "food", ["pancakes", "pancake"], []),
    ("bagel", "Bagel", "food", ["bagel", "bagels"], []),
    ("taco", "Taco", "food", ["taco", "tacos"], []),
    ("burrito", "Burrito", "food", ["burrito", "burritos"], []),
    ("pbj", "Peanut butter and jelly sandwich", "food", ["peanut butter and jelly", "pb&j", "pbj"], []),
    ("smores", "S'more", "food", ["s'mores", "smores"], []),
    ("apple_pie", "Apple pie", "food", ["apple pie"], []),
    ("pumpkin_pie", "Pumpkin pie", "food", ["pumpkin pie"], []),
    ("cereal", "Breakfast cereal", "food", ["cereal"], []),
    ("turkey_dinner", "Turkey as food", "food", ["turkey"], []),
    ("baseball", "Baseball", "festival", ["baseball"], []),
    ("american_football", "American football", "festival", ["football", "super bowl"], []),
    ("basketball", "Basketball", "festival", ["basketball"], []),
    ("snow", "Snow", "place", ["snow", "snowing"], []),
    ("snowman", "Snowman", "place", ["snowman"], []),
    ("school_bus", "School bus", "vehicle", ["school bus"], []),
    ("subway", "New York City Subway", "vehicle", ["subway"], []),
    ("prom", "Prom", "festival", ["prom"], []),
    ("high_school", "High school", "place", ["high school"], []),
    ("college_campus", "Harvard Yard", "place", ["college", "campus", "university"], []),
    ("hiking", "Hiking", "place", ["hiking", "hike"], []),
    ("skiing", "Skiing", "place", ["skiing", "ski"], []),
]


# Display names where the Wikipedia title isn't what a family would say
NAMES = {"cow": "Cow", "tulsi": "Tulsi (holy basil)", "neem": "Neem tree", "rangoli": "Muggu (rangoli)",
         "steel_tumbler": "Steel tumbler (davara)", "charpoy": "Charpoy", "jhoola": "Swing (uyyala)", "monsoon": "Monsoon rains",
         "indian_train": "Train", "rtc_bus": "RTC bus", "rice": "Rice (annam)", "payasam": "Payasam", "bobbatlu": "Bobbatlu",
         "prasadam": "Prasadam", "pulao": "Pulao", "curry_leaves": "Curry leaves", "ragi": "Ragi", "aarti": "Aarti",
         "murukku": "Murukku (jantikalu)", "ariselu": "Ariselu", "village_market": "Market (santha)", "indian_village": "Village (ooru)",
         "paddy_field": "Paddy field (polam)", "dhoti": "Pancha (dhoti)", "chutney": "Pachadi (chutney)", "vada": "Vada (garelu)",
         "coconut_water": "Tender coconut", "paneer_curry": "Paneer curry", "chole": "Chole", "halwa": "Halwa",
         "indian_pickle": "Pickle", "thali": "Full meal (bhojanam)", "curry": "Curry (kura)", "silk_saree": "Pattu saree",
         "diya": "Diya (oil lamp)", "wedding": "Wedding (pelli)", "kite": "Kites (galipatam)", "bangles": "Bangles (gajulu)",
         "bindi": "Bindi (bottu)", "temple": "Temple (gudi)", "auto": "Auto rickshaw", "dal": "Dal (pappu)",
         "ganesh_chaturthi": "Vinayaka Chavithi", "dussehra": "Dasara", "pongal_festival": "Pongal festival", "golu": "Bommala Koluvu",
         "veena": "Veena", "turkey_dinner": "Thanksgiving turkey", "fourth_of_july": "Fourth of July", "american_football": "Football",
         "subway": "Subway", "high_school": "High school", "college_campus": "College", "pbj": "PB&J sandwich",
         "tirupati": "Tirupati temple", "biryani": "Biryani", "sugarcane": "Sugarcane juice", "poha": "Poha (atukulu)",
         "pakora": "Bajji (pakora)", "mortar_pestle": "Grinding stone (rolu)", "tawa": "Tawa", "pressure_cooker": "Pressure cooker",
         "sankranti": "Sankranti", "rangoli_powder": "Rangoli colours"}


# Things from the grandkid's American life: in the library so they can be recognized, but they never pop up for
# the grandkid (they already know them).
AMERICAN = {"thanksgiving", "halloween", "christmas_tree", "fourth_of_july", "hamburger", "pizza", "hot_dog",
            "mac_and_cheese", "pancake", "bagel", "taco", "burrito", "pbj", "smores", "apple_pie", "pumpkin_pie", "cereal",
            "turkey_dinner", "baseball", "american_football", "basketball", "snow", "snowman", "school_bus", "subway",
            "prom", "high_school", "college_campus", "hiking", "skiing", "banana", "mango", "rice", "curry", "cow",
            "scooter", "coconut_tree", "tea"}


def summary(title):
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_"), safe="")
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def first_page_image(title):
    """Some pages have no lead image in their summary; take the first photo on the page instead."""
    url = "https://en.wikipedia.org/api/rest_v1/page/media-list/" + urllib.parse.quote(title.replace(" ", "_"), safe="")
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        return None
    for item in r.json().get("items", []):
        if item.get("type") != "image" or not item.get("srcset"):
            continue
        src = item["srcset"][0]["src"]
        if re.search(r"\.(jpe?g|png)(/|$)", src, re.IGNORECASE) and "logo" not in src.lower() and "icon" not in src.lower():
            return ("https:" + src) if src.startswith("//") else src
    return None


def first_sentence(text):
    m = re.match(r"(.+?[.!?])(\s|$)", text or "")
    return (m.group(1) if m else text or "").strip()


def fetch(item_id, title, library, refresh=False):
    path = os.path.join(OUT, f"{item_id}.jpg")
    if not refresh and item_id in library and os.path.exists(path):
        return "cached"
    data = summary(title)
    thumb = (data.get("thumbnail") or {}).get("source") or first_page_image(title)
    if not thumb:
        return "no image"
    # Wikimedia only serves thumbnails at its standard widths now (asking for 480 px returns 400), so use theirs.
    img = requests.get(thumb, headers=HEADERS, timeout=30)
    img.raise_for_status()
    with open(path, "wb") as f:
        f.write(img.content)
    library[item_id] = {
        "title": data.get("title", title),
        "description": first_sentence(data.get("extract", "")),
        "image": f"images/{item_id}.jpg",
        "credit": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
    }
    return "ok"


def main():
    os.makedirs(OUT, exist_ok=True)
    lib_path = os.path.join(OUT, "library.json")
    saved = json.load(open(lib_path)) if os.path.exists(lib_path) else {"items": {}}
    fetched = saved["items"]
    results = {"ok": 0, "cached": 0}
    for item_id, title, category, aliases, lexicon_ids in ITEMS:
        try:
            status = fetch(item_id, title, fetched, refresh="--refresh" in sys.argv)
        except requests.RequestException as e:
            status = f"failed ({e.__class__.__name__})"
        if item_id in fetched:
            fetched[item_id].update({"name": NAMES.get(item_id, fetched[item_id]["title"]), "category": category,
                                     "region": "us" if item_id in AMERICAN else "in",
                                     "aliases": aliases, "lexicon_ids": lexicon_ids, "wikipedia": title})
        results[status] = results.get(status, 0) + 1
        if status not in ("ok", "cached"):
            print(f"  {item_id:18} {title:40} {status}")
        time.sleep(0.1)  # be polite to Wikipedia
    known = {i[0] for i in ITEMS}
    saved["items"] = {k: v for k, v in fetched.items() if k in known}
    saved["_about"] = "Built by tools/build_images.py. Pictures and descriptions from Wikipedia (see each item's credit link)."
    json.dump(saved, open(lib_path, "w"), ensure_ascii=False, indent=1)
    print(results, f"-> {len(saved['items'])} items in images/library.json")


if __name__ == "__main__":
    main()
