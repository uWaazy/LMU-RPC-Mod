import re
import unicodedata

FALLBACK_ASSET = "lmu_logo_default"
TRUNCATED_LEN = 29

SERIES_SUFFIX = re.compile(r":[A-Za-z0-9]+$")
YEAR = re.compile(r"\b(20\d{2})\b")

MODEL_TABLE = {
    "aston martin valkyrie lmh": ("car_aston_martin_valkyrie", "Aston Martin Valkyrie", {}),
    "toyota tr010": ("car_toyota_gr010", "Toyota TR010", {}),
    "cadillac v-series.r": ("car_cadillac_v_series_r", "Cadillac V-Series.R", {}),
    "bmw m hybrid v8": ("car_bmw_m_hybrid_v8", "BMW M Hybrid V8", {}),
    "genesis gmr-001": ("car_genesis_gmr001", "Genesis GMR-001", {}),
    "alpine a424": ("car_alpine_a424", "Alpine A424", {}),
    "ferrari 499p": ("car_ferrari_499p", "Ferrari 499P", {}),
    "peugeot 9x8": ("car_peugeot_9x8", "Peugeot 9X8", {"2024": "car_peugeot_9x8_2024"}),
    "mclaren 720s lmgt3 evo": ("car_mclaren_720s_gt3", "McLaren 720S LMGT3 Evo", {}),
    "chevrolet corvette z06 lmgt3.r": ("car_corvette_z06_gt3", "Chevrolet Corvette Z06 LMGT3.R", {}),
    "ferrari 296 lmgt3 evo": ("car_ferrari_296_gt3", "Ferrari 296 LMGT3 Evo", {}),
    "aston martin vantage amr lmgt3": ("car_aston_martin_vantage_gt3", "Aston Martin Vantage AMR LMGT3", {}),
    "bmw m4 lmgt3": ("car_bmw_m4_gt3", "BMW M4 LMGT3", {}),
    "mercedes-amg lmgt3": ("car_mercedes_amg_gt3", "Mercedes-AMG LMGT3", {}),
    "ford mustang lmgt3": ("car_ford_mustang_gt3", "Ford Mustang LMGT3", {}),
    "adess ad25 lmp3": ("car_adess_03", "ADESS AD25 LMP3", {}),
    "lexus rcf lmgt3": ("car_lexus_rcf_gt3", "Lexus RC F LMGT3", {}),
    "oreca 07": (
        "car_oreca_07_2026",
        "Oreca 07 Gibson",
        {"2023": "car_oreca_07_2023", "2024": "car_oreca_07_2024"},
    ),
}

KEYWORD_FALLBACK = [
    (("valkyrie",), "car_aston_martin_valkyrie", "Aston Martin Valkyrie"),
    (("gr010",), "car_toyota_gr010", "Toyota GR010"),
    (("tr010",), "car_toyota_gr010", "Toyota TR010"),
    (("v-series",), "car_cadillac_v_series_r", "Cadillac V-Series.R"),
    (("bmw", "hybrid"), "car_bmw_m_hybrid_v8", "BMW M Hybrid V8"),
    (("genesis",), "car_genesis_gmr001", "Genesis GMR-001"),
    (("a424",), "car_alpine_a424", "Alpine A424"),
    (("499p",), "car_ferrari_499p", "Ferrari 499P"),
    (("9x8",), "car_peugeot_9x8", "Peugeot 9X8"),
    (("963",), "car_porsche_963", "Porsche 963"),
    (("glickenhaus",), "car_glickenhaus_007", "Glickenhaus SCG 007"),
    (("isotta",), "car_isotta_fraschini", "Isotta Fraschini"),
    (("sc63",), "car_lamborghini_sc63", "Lamborghini SC63"),
    (("vanwall",), "car_vanwall_680", "Vanwall Vandervell"),
    (("mustang",), "car_ford_mustang_gt3", "Ford Mustang LMGT3"),
    (("720s",), "car_mclaren_720s_gt3", "McLaren 720S LMGT3 Evo"),
    (("mercedes",), "car_mercedes_amg_gt3", "Mercedes-AMG LMGT3"),
    (("bmw", "m4"), "car_bmw_m4_gt3", "BMW M4 LMGT3"),
    (("vantage", "gte"), "car_aston_martin_vantage_gte", "Aston Martin Vantage GTE"),
    (("vantage",), "car_aston_martin_vantage_gt3", "Aston Martin Vantage AMR LMGT3"),
    (("corvette", "c8"), "car_corvette_c8r_gte", "Chevrolet Corvette C8.R"),
    (("corvette",), "car_corvette_z06_gt3", "Chevrolet Corvette Z06 LMGT3.R"),
    (("296",), "car_ferrari_296_gt3", "Ferrari 296 LMGT3 Evo"),
    (("488",), "car_ferrari_488_gte", "Ferrari 488 GTE"),
    (("huracan",), "car_lamborghini_huracan_gt3", "Lamborghini Huracan GT3"),
    (("lexus",), "car_lexus_rcf_gt3", "Lexus RC F LMGT3"),
    (("911", "rsr"), "car_porsche_911_rsr", "Porsche 911 RSR-19"),
    (("911",), "car_porsche_911_gt3", "Porsche 911 GT3 R"),
    (("ginetta",), "car_ginetta_g61", "Ginetta G61-LT-P325-Evo"),
    (("ligier",), "car_ligier_js_p325", "Ligier JS P325"),
    (("duqueine",), "car_duqueine_d09", "Duqueine D09 LMP3"),
    (("adess",), "car_adess_03", "ADESS AD25 LMP3"),
    (("oreca",), "car_oreca_07_2026", "Oreca 07 Gibson"),
]


def normalize(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def clean_entry_name(entry_name):
    return SERIES_SUFFIX.sub("", entry_name or "").strip()


def entry_year(entry_name):
    m = YEAR.search(entry_name or "")
    return m.group(1) if m else ""


def _from_table(key, year):
    entry = MODEL_TABLE.get(key)
    if entry is None and len(key.encode("utf-8")) >= TRUNCATED_LEN:
        for table_key, value in MODEL_TABLE.items():
            if table_key.startswith(key):
                entry = value
                break
    if entry is None:
        return None
    asset, name, variants = entry
    return variants.get(year, asset), name


def _from_keywords(key):
    for words, asset, name in KEYWORD_FALLBACK:
        if all(w in key for w in words):
            return asset, name
    return None


def resolve_car(model, year=""):
    key = normalize(model)
    found = _from_table(key, year)
    if found:
        return found[0], found[1], "table"
    found = _from_keywords(key)
    if found:
        return found[0], found[1], "keywords"
    return FALLBACK_ASSET, (model or "").strip(), "unknown"
