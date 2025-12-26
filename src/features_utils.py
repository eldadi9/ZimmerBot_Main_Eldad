import json
from pathlib import Path
from typing import List, Dict, Any


def _project_root() -> Path:
    # src/features_utils.py -> project root is one level above src
    return Path(__file__).resolve().parents[1]


def _data_dir() -> Path:
    return _project_root() / "data"


def _catalog_path(json_path: str = "data/features_catalog.json") -> Path:
    # allow both default relative path and custom absolute path
    p = Path(json_path)
    if p.is_absolute():
        return p
    return _project_root() / p


def _default_catalog() -> Dict[str, Any]:
    # Catalog focused on families. Keys are what you put in Swagger "features".
    return {
        "version": 1,
        "title": "ZimmerBot Features Catalog",
        "categories": [
            {
                "id": "internet",
                "label_he": "אינטרנט ותקשורת",
                "items": [
                    {"key": "internet", "label_he": "אינטרנט"},
                    {"key": "fast_wifi", "label_he": "ווייפיי מהיר"},
                    {"key": "fiber_wifi", "label_he": "סיב אופטי"},
                    {"key": "wifi_mesh", "label_he": "רשת Mesh"},
                    {"key": "work_desk", "label_he": "עמדת עבודה"},
                ],
            },
            {
                "id": "kids",
                "label_he": "ילדים ומשפחות",
                "items": [
                    {"key": "kids_friendly", "label_he": "ידידותי לילדים"},
                    {"key": "baby_bed", "label_he": "מיטת תינוק"},
                    {"key": "baby_chair", "label_he": "כיסא אוכל לתינוק"},
                    {"key": "baby_bath", "label_he": "אמבט לתינוק"},
                    {"key": "baby_monitor", "label_he": "מוניטור תינוק"},
                    {"key": "stroller_access", "label_he": "גישה נוחה לעגלות"},
                    {"key": "playground", "label_he": "מתקן משחקים"},
                    {"key": "kids_pool", "label_he": "בריכת ילדים"},
                    {"key": "game_room", "label_he": "חדר משחקים"},
                    {"key": "board_games", "label_he": "משחקי קופסא"},
                    {"key": "kids_tv", "label_he": "ערוצי ילדים"},
                    {"key": "family_suite", "label_he": "סוויטה למשפחה"},
                    {"key": "safe_stairs", "label_he": "מדרגות בטוחות"},
                    {"key": "stair_gate", "label_he": "שער בטיחות למדרגות"},
                    {"key": "window_guards", "label_he": "סורגי בטיחות לחלונות"},
                ],
            },
            {
                "id": "outdoor",
                "label_he": "חוץ וחצר",
                "items": [
                    {"key": "private_yard", "label_he": "חצר פרטית"},
                    {"key": "garden", "label_he": "גינה"},
                    {"key": "bbq", "label_he": "מנגל"},
                    {"key": "gas_bbq", "label_he": "מנגל גז"},
                    {"key": "outdoor_dining", "label_he": "פינת אוכל חיצונית"},
                    {"key": "hammock", "label_he": "ערסל"},
                    {"key": "fire_pit", "label_he": "מדורת גן"},
                    {"key": "outdoor_shower", "label_he": "מקלחת חוץ"},
                    {"key": "parking", "label_he": "חניה"},
                    {"key": "covered_parking", "label_he": "חניה מקורה"},
                    {"key": "ev_charger", "label_he": "טעינה לרכב חשמלי"},
                ],
            },
            {
                "id": "pool_spa",
                "label_he": "בריכה וספא",
                "items": [
                    {"key": "pool", "label_he": "בריכה"},
                    {"key": "heated_pool", "label_he": "בריכה מחוממת"},
                    {"key": "private_pool", "label_he": "בריכה פרטית"},
                    {"key": "jacuzzi", "label_he": "גקוזי"},
                    {"key": "hot_tub", "label_he": "אמבט חם"},
                    {"key": "sauna", "label_he": "סאונה"},
                    {"key": "steam_room", "label_he": "חמאם"},
                ],
            },
            {
                "id": "kitchen",
                "label_he": "מטבח ואוכל",
                "items": [
                    {"key": "kitchen", "label_he": "מטבח"},
                    {"key": "full_kitchen", "label_he": "מטבח מאובזר"},
                    {"key": "kosher_kitchen", "label_he": "מטבח כשר"},
                    {"key": "shabbat_hotplate", "label_he": "פלטת שבת"},
                    {"key": "shabbat_urn", "label_he": "מיחם שבת"},
                    {"key": "coffee_machine", "label_he": "מכונת קפה"},
                    {"key": "espresso_machine", "label_he": "מכונת אספרסו"},
                    {"key": "dishwasher", "label_he": "מדיח כלים"},
                    {"key": "microwave", "label_he": "מיקרוגל"},
                    {"key": "oven", "label_he": "תנור"},
                    {"key": "toaster", "label_he": "טוסטר"},
                    {"key": "blender", "label_he": "בלנדר"},
                    {"key": "water_filter", "label_he": "מסנן מים"},
                    {"key": "high_chair", "label_he": "כיסא אוכל"},
                ],
            },
            {
                "id": "comfort",
                "label_he": "נוחות",
                "items": [
                    {"key": "ac", "label_he": "מיזוג אוויר"},
                    {"key": "heating", "label_he": "חימום"},
                    {"key": "floor_heating", "label_he": "חימום תת רצפתי"},
                    {"key": "fireplace", "label_he": "קמין"},
                    {"key": "blackout_curtains", "label_he": "וילונות האפלה"},
                    {"key": "quiet_room", "label_he": "חדר שקט"},
                    {"key": "washing_machine", "label_he": "מכונת כביסה"},
                    {"key": "dryer", "label_he": "מייבש כביסה"},
                ],
            },
            {
                "id": "entertainment",
                "label_he": "בידור",
                "items": [
                    {"key": "smart_tv", "label_he": "טלוויזיה חכמה"},
                    {"key": "netflix", "label_he": "נטפליקס"},
                    {"key": "youtube", "label_he": "יוטיוב"},
                    {"key": "speaker", "label_he": "רמקול"},
                    {"key": "projector", "label_he": "מקרן"},
                    {"key": "playstation", "label_he": "פלייסטיישן"},
                ],
            },
            {
                "id": "safety",
                "label_he": "בטיחות ואבטחה",
                "items": [
                    {"key": "safe_room", "label_he": "ממ\"ד"},
                    {"key": "cctv_outdoor", "label_he": "מצלמות חוץ"},
                    {"key": "alarm", "label_he": "אזעקה"},
                    {"key": "smoke_detector", "label_he": "גלאי עשן"},
                    {"key": "fire_extinguisher", "label_he": "מטף"},
                    {"key": "first_aid", "label_he": "ערכת עזרה ראשונה"},
                ],
            },
            {
                "id": "accessibility",
                "label_he": "נגישות",
                "items": [
                    {"key": "accessible", "label_he": "נגיש"},
                    {"key": "no_stairs", "label_he": "ללא מדרגות"},
                    {"key": "accessible_bathroom", "label_he": "שירותים נגישים"},
                    {"key": "wide_doors", "label_he": "דלתות רחבות"},
                ],
            },
            {
                "id": "policies",
                "label_he": "מדיניות",
                "items": [
                    {"key": "pets_allowed", "label_he": "חיות מחמד מותר"},
                    {"key": "no_smoking", "label_he": "ללא עישון"},
                    {"key": "self_checkin", "label_he": "צק אין עצמי"},
                    {"key": "late_checkout", "label_he": "צק אאוט מאוחר"},
                ],
            },
        ],
    }


def ensure_catalog_exists(json_path: str = "data/features_catalog.json", force: bool = False) -> Path:
    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    path = _catalog_path(json_path)

    if force or (not path.exists()):
        path.write_text(json.dumps(_default_catalog(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    # Validate existing file
    try:
        txt = path.read_text(encoding="utf-8").strip()
        if not txt:
            raise ValueError("Empty file")
        json.loads(txt)
    except Exception:
        # overwrite broken/empty json
        path.write_text(json.dumps(_default_catalog(), ensure_ascii=False, indent=2), encoding="utf-8")

    return path


def load_catalog(json_path: str = "data/features_catalog.json") -> Dict[str, Any]:
    path = ensure_catalog_exists(json_path=json_path, force=False)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def all_feature_keys(catalog: Dict[str, Any]) -> set:
    keys = set()
    for cat in catalog.get("categories", []):
        for item in cat.get("items", []):
            k = str(item.get("key", "")).strip()
            if k:
                keys.add(k)
    return keys


def build_features_string(selected_keys: List[str], json_path: str = "data/features_catalog.json") -> str:
    catalog = load_catalog(json_path)
    valid = all_feature_keys(catalog)

    cleaned = []
    for k in selected_keys:
        k2 = str(k).strip()
        if not k2:
            continue
        # normalize input a bit (Internet -> internet)
        k2_norm = k2.replace(" ", "_").lower()
        if k2 in valid:
            cleaned.append(k2)
        elif k2_norm in valid:
            cleaned.append(k2_norm)

    # unique preserve order
    out = []
    seen = set()
    for k in cleaned:
        if k not in seen:
            out.append(k)
            seen.add(k)

    return ",".join(out)


if __name__ == "__main__":
    # Quick CLI
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="Create/overwrite catalog file")
    parser.add_argument("--show", action="store_true", help="Print all available keys")
    parser.add_argument("--build", nargs="*", default=None, help="Build features string from keys")
    args = parser.parse_args()

    if args.init:
        p = ensure_catalog_exists(force=True)
        print(f"OK: created {p}")

    cat = load_catalog()
    if args.show:
        keys = sorted(list(all_feature_keys(cat)))
        print("\n".join(keys))

    if args.build is not None:
        print(build_features_string(args.build))
    elif not args.init and not args.show:
        # default demo
        print(build_features_string(["fast_wifi", "kids_friendly", "bbq", "Internet"]))
