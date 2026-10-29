"""
Extends data/hcmc_flood_blackspots.json with streets that credible sources report as flooded.

Candidates come from (a) data/news_candidates.json (articles verified earlier) and (b) the flood lists
below. Each candidate is geocoded with the validated geocoder (road feature, matching name, inside HCMC,
Nominatim and Photon agreeing when both answer). Streets that cannot be located trustworthily are
reported, never guessed. The original 78 entries are left untouched.

Usage: python scripts/expand_gazetteer.py [--dry-run]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.evaluation import normalize_name
from app.services.geocoding_service import _lookup_gazetteer, geocode_street

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PATH = os.path.join(ROOT, "data", "hcmc_flood_blackspots.json")
RAIN, TIDE = "mưa lớn", "triều cường"

SRC = {
    "CSGT_2026": "https://tienphong.vn/122-diem-co-nguy-co-ngap-tai-tphcm-csgt-canh-bao-khan-post1882808.tpo",
    "TT23_2025": "https://tuoitre.vn/23-tuyen-duong-ngap-do-trieu-cuong-o-tp-hcm-nguoi-dan-can-ghi-nho-20251120193639188.htm",
    "VOH13_2024": "https://voh.com.vn/tin-tp-ho-chi-minh/tphcm-diem-ten-13-tuyen-duong-he-mua-la-ngap-526734.html",
    "TT_2026_01": "https://tuoitre.vn/tu-hang-xanh-den-quoc-lo-13-vi-sao-nhieu-tuyen-duong-cu-mua-la-ngap-20260129133331259.htm",
    "VNE22_2020": "https://vnexpress.net/tp-hcm-chi-con-22-duong-bi-ngap-4112738.html",
    "CAFEF12_2026": "https://cafef.vn/12-tuyen-duong-o-tphcm-ngap-sau-mua-lon-co-noi-ngap-hon-1-met-188261001174131262.chn",
    "VNN_2017": "https://vietnamnet.vn/sai-gon-ngap-duong-pho-ket-cung-sau-mua-lon-373934.html",
    "VTC_2020": "https://vtcnews.vn/nhung-noi-cu-mua-la-ngap-o-tphcm-ar550142.html",
    "SGGP_2025_10": "https://www.sggp.org.vn/so-xay-dung-tphcm-neu-giai-phap-ung-pho-voi-trieu-cuong-post820852.html",
    "VNE_2016": "https://vnexpress.net/cang-chong-cang-ngap-3421278.html",
}

# (street, cause, source key)
LISTS = [
    *[(n, RAIN, "CSGT_2026") for n in ["Hồ Học Lãm", "Trần Văn Giàu", "Vĩnh Lộc", "Đỗ Mười", "Võ Nguyên Giáp", "Mai Chí Thọ",
                                       "Tô Ngọc Vân", "Tố Hữu", "Lương Định Của", "Phạm Văn Đồng", "Nguyễn Văn Linh", "Ung Văn Khiêm"]],
    *[(n, TIDE, "CSGT_2026") for n in ["Trần Xuân Soạn", "Lê Văn Lương", "Phạm Hữu Lầu", "Nguyễn Hữu Thọ", "Võ Văn Kiệt",
                                       "Trần Hưng Đạo", "Phạm Thế Hiển", "Dương Bá Trạc", "Nguyễn Văn Hưởng", "Hà Huy Giáp"]],
    *[(n, TIDE, "TT23_2025") for n in ["Calmette", "Bình Quới", "Huỳnh Tấn Phát", "Đào Sư Tích", "Nguyễn Bình", "Thích Quảng Đức", "Hồ Văn Cống"]],
    *[(n, RAIN, "VOH13_2024") for n in ["Phan Anh", "Lê Đức Thọ", "Quang Trung", "Nguyễn Văn Khối", "Hồ Học Lãm", "Đặng Thị Rành",
                                        "Dương Văn Cam", "Kha Vạn Cân", "Bạch Đằng", "Quốc Hương", "Nguyễn Văn Hưởng"]],
    *[(n, RAIN, "TT_2026_01") for n in ["Đinh Bộ Lĩnh", "Ung Văn Khiêm", "Bạch Đằng", "Nguyễn Hữu Cảnh", "Kinh Dương Vương",
                                        "An Dương Vương", "Trần Xuân Soạn", "Lương Định Của", "Tân Kỳ Tân Quý"]],
    *[(n, RAIN, "VNE22_2020") for n in ["Nguyễn Văn Khối", "Đào Sư Tích", "Lê Văn Lương", "Hồ Ngọc Lãm", "Phan Văn Hớn", "Nguyễn Văn Hưởng",
                                        "Nguyễn Hữu Cảnh", "Điện Biên Phủ", "Phan Huy Ích", "Ung Văn Khiêm", "Quốc Hương", "Phạm Văn Chiêu",
                                        "Bình Lợi", "Lê Đức Thọ", "Phạm Văn Đồng", "Tô Ngọc Vân", "Kha Vạn Cân", "Dương Văn Cam",
                                        "Đặng Thị Rành", "Nguyễn Văn Quá"]],
    *[(n, "cả hai", "CAFEF12_2026") for n in ["Tên Lửa", "Phan Anh", "Quang Trung", "Bà Triệu", "Phạm Văn Chiêu", "Lê Đức Thọ", "Phan Huy Ích",
                                              "Phan Văn Hớn", "Nguyễn Văn Quá", "Lương Định Của", "Bình Quới", "Hồ Học Lãm", "Nguyễn Văn Khối"]],
    *[(n, RAIN, "VNN_2017") for n in ["Hoàng Minh Giám", "Nguyễn Thái Sơn", "Nguyễn Kiệm"]],
    *[(n, RAIN, "VTC_2020") for n in ["Xô Viết Nghệ Tĩnh", "Phan Đăng Lưu", "Nguyễn Xí", "Đặng Văn Bi", "Hoàng Hữu Nam", "Nguyễn Xiển",
                                      "Nguyễn Cư Trinh", "Đỗ Xuân Hợp", "Lũy Bán Bích", "Kinh Dương Vương", "Hồ Ngọc Lãm", "Khuông Việt",
                                      "Phạm Phú Thứ", "Đồng Đen", "Bàu Cát", "Hồng Lạc", "Hòa Bình"]],
    *[(n, TIDE, "SGGP_2025_10") for n in ["Bình Quới", "Trần Xuân Soạn", "Huỳnh Tấn Phát", "Thanh Đa"]],
    ("Trần Não", RAIN, "VNE_2016"),
]

# Not single points: highways run for km, wards/landmarks/generic names are not streets
SKIP_PREFIX = ("quốc lộ", "xa lộ", "đường số", "song hành", "đường song hành", "hẻm", "hầm", "cầu", "khu ", "bến ")
SKIP_NAMES = {"thảo điền", "linh đông", "liên phường"}


def causes_label(causes):
    return "cả hai" if len(causes) > 1 or "cả hai" in causes else next(iter(causes))


def collect():
    cands = {}
    for name, cause, src in LISTS:
        c = cands.setdefault(normalize_name(name), {"street": name, "causes": set(), "sources": set()})
        c["causes"].add(cause)
        c["sources"].add(SRC[src])
    with open(os.path.join(ROOT, "data", "news_candidates.json"), encoding="utf-8") as f:
        for a in json.load(f):
            cause = {"mưa": RAIN, "triều cường": TIDE}.get(a["flood_type"], "cả hai")
            for name in a["streets"]:
                c = cands.setdefault(normalize_name(name), {"street": name, "causes": set(), "sources": set()})
                c["causes"].add(cause)
                c["sources"].add(a["url"])
    return cands


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(PATH, encoding="utf-8") as f:
        data = json.load(f)
    existing = {normalize_name(s["street"]) for s in data["blackspots"]}

    cands = collect()
    todo = []
    for key, c in sorted(cands.items()):
        low = c["street"].lower()
        if key in existing or _lookup_gazetteer(low) or low.startswith(SKIP_PREFIX) or low in SKIP_NAMES:
            continue
        todo.append(c)
    print(f"{len(cands)} distinct candidate streets, {len(todo)} to geocode")

    added, review, failed = [], [], []
    for i, c in enumerate(todo, 1):
        geo = geocode_street(c["street"])
        if geo is None:
            failed.append(c["street"])
            print(f"[{i}/{len(todo)}] {c['street']}: NOT FOUND")
            continue
        entry = {
            "street": c["street"], "district": None, "ward": None,
            "lat": geo["lat"], "lon": geo["lon"], "radius_m": 350.0,
            "cause": causes_label(c["causes"]), "landmark": None,
            "sources": sorted(c["sources"]),
            "geocode_source": geo["geocode_source"], "geocode_confidence": geo["geocode_confidence"],
            "address_hint": geo.get("address_hint", ""),
            "needs_review": geo["geocode_confidence"] != "agreed",
            "added_in": "1.1.0",
        }
        added.append(entry)
        if entry["needs_review"]:
            review.append(entry["street"])
        print(f"[{i}/{len(todo)}] {c['street']}: {geo['geocode_confidence']} ({geo['lat']}, {geo['lon']})")

    print(f"\nadded {len(added)} | agreed {len(added) - len(review)} | single-source (needs review) {len(review)} | not found {len(failed)}")
    print("NOT FOUND:", ", ".join(failed))
    if args.dry_run:
        return
    data["blackspots"].extend(added)
    data["metadata"]["version"] = "1.1.0"
    data["metadata"]["updated_at"] = "2026-10-23"
    data["metadata"]["extension_note"] = (
        "Entries with added_in=1.1.0 were added by scripts/expand_gazetteer.py from the listed source articles; "
        "coordinates are one geocoded point on the street, not the flooded segment. needs_review=true marks "
        "single-service geocodes that should be checked on a map."
    )
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {PATH}: {len(data['blackspots'])} blackspots total")


if __name__ == "__main__":
    main()
