"""Project-wide constants: paths, business rules and lookup tables. Colours live in src/theme.py."""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parent.parent
RAW_XLSX = ROOT / "B2B_Transaction_Data_.xlsx"
DATA_DIR = ROOT / "data"
PARQUET = DATA_DIR / "transactions.parquet"
CLEANING_LOG = DATA_DIR / "cleaning_log.json"

# --------------------------------------------------------------------------- main categories
# 307 raw categories are folded into 8 main categories with ordered keyword rules
# (first match wins). Anything unmatched falls into "Other".
MAIN_CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Puzzles, Games & Stationery", (
        "Puzzle", "Bulmaca", "Masa Setleri", "Oyun Kitapları", "Kutu Oyun", "Oyuncak", "Hobi", "Defter",
        "Ajanda", "Takvim", "Kalem", "Kart Zarf", "Kap Kağıt", "Eğitici Oyunlar")),
    # Family/pregnancy health titles contain "Çocuk", so they must be matched before the Children's rule.
    ("Personal Growth & Health", ("Aile - Çocuk", "Hamilelik ve Çocuk Sağlığı")),
    ("Children's Books", (
        "Çocuk", "Masal", "Okul Öncesi", "Boyama", "Çıkartma", "Preschool", "Children",
        "6+ Yaş", "İlk Yaş", "Storybook", "Characters", "Eğitim Etkinlik", "Eğitim/Etkinlik",
        "Sesli")),
    ("Exam & Education", (
        "Test", "YKS", "LGS", "KPSS", "DGS", "ALES", "YDS", "KPDS", "TOEFL", "Sınav", "Exam",
        "Tüm Dersler", "Matematik", "Fizik", "Kimya", "Biyoloji", "Türkçe", "Fen ve",
        "Sosyal Bilgiler", "Coğrafya", "Okul Kitapları", "Ders", "Öğretmen", "Eğitim",
        "Dil ve Anlatım", "SPK", "İnkılap", "Din Kültürü", "Graded", "Grammar", "Phrase",
        "Dictionary", "Sözlük")),
    ("Fiction & Literature", (
        "Roman", "Öykü", "Klasik", "Classics", "Polisiye", "Korku", "Fantastik", "Fantasy",
        "Bilim Kurgu", "Macera", "Şiir", "Deneme", "Edebiyat", "Literature", "Anlatı",
        "Tiyatro", "Oyunları", "Mektup", "Günlük Anı", "Mizah", "Destan", "Mitoloji",
        "Kurgu", "Antoloji", "Fıkra", "Senaryo", "Karikatür", "Erotik", "Mystery",
        "Halk Ozan")),
    ("History, Politics & Religion", (
        "Tarih", "History", "Atatürk", "Politika", "Politics", "Osmanlı", "Ermeni",
        "Avrupa Birliği", "Uluslararası", "Devlet Adam", "Türkiye", "Kamu", "Sivil Toplum",
        "İslam", "Tasavvuf", "Din", "Alevilik", "Hristiyan", "Musevi", "Budizm", "İnanç",
        "Religion", "Biyografi", "Biography")),
    ("Personal Growth & Health", (
        "Kişisel Gelişim", "Psikoloji", "Sağl", "Beslenme", "Kadın", "Aile", "Cinsellik",
        "Hamilelik", "Ergenlik", "Uyuşturucu", "Health", "Self Help", "Yoga", "Bilgelik",
        "Mind and Spirit", "Astroloji", "Parapsikoloji", "Kehanet", "Rüya")),
    ("Science, Philosophy & Society", (
        "Felsefe", "Bilim", "Sosyoloji", "Antropoloji", "Etnoloji", "Astronomi", "Ekoloji",
        "Botanik", "Jeoloji", "Zooloji", "Tıp", "Anatomi", "Arkeoloji", "Medya", "İletişim",
        "Hukuk", "Sosyal Bilimler", "Mühendislik", "Bilgisayar", "Bilişim", "İstatistik",
        "Genel İlgi", "Ekonomi", "İktisat", "Finans", "Borsa", "Yönetim", "İşletme",
        "Pazarlama", "İnsan Kaynakları", "Dış Ticaret", "Maliye", "İş Adamları", "Business")),
]
OTHER_CATEGORY = "Other (Arts, Lifestyle, Languages)"
# Display order (by 2020 revenue). src/theme.py assigns colours in this order, so they never change with filters.
MAIN_CATEGORIES: list[str] = [
    "Fiction & Literature", "Children's Books", "Exam & Education", "Personal Growth & Health",
    "History, Politics & Religion", "Science, Philosophy & Society", OTHER_CATEGORY,
    "Puzzles, Games & Stationery",
]

# --------------------------------------------------------------------------- customer groups
# Derived from each customer's share of full-year revenue (the raw data has no group field).
CUSTOMER_GROUPS: list[tuple[str, float]] = [  # (name, upper cumulative customer-rank share)
    ("Key account", 0.10),
    ("Large", 0.30),
    ("Medium", 0.60),
    ("Small", 1.00),
]

# --------------------------------------------------------------------------- document series
DOC_SERIES = ["BAD", "BSR", "DPF", "DPE", "MUH"]

# --------------------------------------------------------------------------- analysis settings
FORECAST_WEEKS = 8
TEST_WEEKS = 8
DATA_GAP_DAYS = 7          # a pause between trading days longer than this is annotated
ABC_CUTS = (0.80, 0.95)    # cumulative revenue share -> A / B / C
XYZ_CUTS = (0.5, 1.0)      # CV of weekly units -> X / Y / Z
SLOW_MOVER_DAYS = 90
RANDOM_STATE = 42

ABC_XYZ_POLICY: dict[str, str] = {
    "AX": "High value, steady demand: automate replenishment, keep low safety stock, negotiate volume contracts.",
    "AY": "High value, variable demand: forecast weekly, hold moderate safety stock, review often.",
    "AZ": "High value, erratic demand: make-to-order or vendor-managed stock; avoid large buffers.",
    "BX": "Mid value, steady demand: periodic review with standard safety stock.",
    "BY": "Mid value, variable demand: periodic review, seasonal adjustments.",
    "BZ": "Mid value, erratic demand: keep minimal stock, order on demand where lead time allows.",
    "CX": "Low value, steady demand: bulk ordering, simple min/max rules.",
    "CY": "Low value, variable demand: min/max with infrequent review.",
    "CZ": "Low value, erratic demand: candidates for delisting or drop-shipping.",
}

# --------------------------------------------------------------------------- RFM
RFM_SEGMENT_ACTIONS: dict[str, str] = {
    "Champions": "Reward them: early access to new titles, volume bonuses, ask for referrals.",
    "Loyal Customers": "Upsell higher-value categories; offer loyalty pricing tiers.",
    "Potential Loyalists": "Offer a membership/contract programme and recommend related titles.",
    "New Customers": "Onboard: catalogue walkthrough, first-reorder incentive.",
    "Promising": "Build habit with targeted promotions on their best-selling categories.",
    "Need Attention": "Time-limited offers based on past purchases; check service issues.",
    "About to Sleep": "Reactivate with personalised recommendations and a reorder reminder.",
    "At Risk": "Account manager call; win-back discount on their top categories.",
    "Can't Lose Them": "Priority outreach from senior sales; find out why orders stopped.",
    "Hibernating": "Low-cost reactivation campaign; new-arrivals newsletter.",
    "Lost": "Only re-engage with very low-cost channels; otherwise deprioritise.",
}
AT_RISK_SEGMENTS = ("Can't Lose Them", "At Risk", "About to Sleep")

# --------------------------------------------------------------------------- provinces
# Approximate coordinates (lat, lon) of each province capital, keyed by the spelling used in the data.
PROVINCE_COORDS: dict[str, tuple[float, float]] = {
    "ADANA": (37.00, 35.32), "ADIYAMAN": (37.76, 38.28), "AFYON": (38.76, 30.54),
    "AGRI": (39.72, 43.05), "AKSARAY": (38.37, 34.03), "AMASYA": (40.65, 35.83),
    "ANKARA": (39.93, 32.86), "ANTALYA": (36.89, 30.71), "ARDAHAN": (41.11, 42.70),
    "ARTVIN": (41.18, 41.82), "AYDIN": (37.85, 27.85), "BALIKESIR": (39.65, 27.88),
    "BARTIN": (41.64, 32.34), "BATMAN": (37.88, 41.13), "BAYBURT": (40.26, 40.23),
    "BILECIK": (40.14, 29.98), "BINGÖL": (38.88, 40.50), "BITLIS": (38.40, 42.11),
    "BOLU": (40.74, 31.61), "BURDUR": (37.72, 30.29), "BURSA": (40.19, 29.06),
    "DENIZLI": (37.78, 29.09), "DIYARBAKIR": (37.91, 40.24), "DÜZCE": (40.84, 31.16),
    "EDIRNE": (41.68, 26.56), "ELAZIG": (38.67, 39.22), "ERZINCAN": (39.75, 39.49),
    "ERZURUM": (39.90, 41.27), "ESKISEHIR": (39.78, 30.52), "GAZIANTEP": (37.07, 37.38),
    "GIRESUN": (40.91, 38.39), "GÜMÜSHANE": (40.46, 39.48), "HATAY": (36.20, 36.16),
    "IGDIR": (39.92, 44.04), "ISPARTA": (37.76, 30.55), "ISTANBUL": (41.01, 28.98),
    "IZMIR": (38.42, 27.14), "IÇEL": (36.81, 34.64), "K.MARAS": (37.58, 36.94),
    "KARABÜK": (41.20, 32.62), "KARAMAN": (37.18, 33.22), "KARS": (40.60, 43.10),
    "KASTAMONU": (41.38, 33.78), "KAYSERI": (38.73, 35.49), "KIRKLARELI": (41.73, 27.22),
    "KIRSEHIR": (39.15, 34.16), "KOCAELI": (40.77, 29.92), "KONYA": (37.87, 32.48),
    "KÜTAHYA": (39.42, 29.98), "MALATYA": (38.35, 38.31), "MANISA": (38.61, 27.43),
    "MARDIN": (37.31, 40.74), "MUGLA": (37.22, 28.36), "MUS": (38.74, 41.49),
    "NEVSEHIR": (38.62, 34.71), "NIGDE": (37.97, 34.68), "ORDU": (40.98, 37.88),
    "OSMANIYE": (37.07, 36.25), "RIZE": (41.02, 40.52), "SAKARYA": (40.69, 30.44),
    "SAMSUN": (41.29, 36.33), "SANLIURFA": (37.17, 38.79), "SIIRT": (37.93, 41.94),
    "SINOP": (42.03, 35.15), "SIVAS": (39.75, 37.02), "TEKIRDAG": (40.98, 27.51),
    "TOKAT": (40.31, 36.55), "TRABZON": (41.00, 39.72), "TUNCELI": (39.11, 39.55),
    "USAK": (38.68, 29.41), "VAN": (38.49, 43.38), "YALOVA": (40.65, 29.27),
    "YOZGAT": (39.82, 34.81), "ZONGULDAK": (41.46, 31.79), "ÇANAKKALE": (40.15, 26.41),
    "ÇANKIRI": (40.60, 33.61), "ÇORUM": (40.55, 34.95),
}
UNKNOWN_CITY = "UNKNOWN"

# Display names with Turkish characters, keyed by the spelling used in the data (display only).
PROVINCE_NAMES: dict[str, str] = {
    "ADANA": "Adana", "ADIYAMAN": "Adıyaman", "AFYON": "Afyonkarahisar", "AGRI": "Ağrı", "AKSARAY": "Aksaray",
    "AMASYA": "Amasya", "ANKARA": "Ankara", "ANTALYA": "Antalya", "ARDAHAN": "Ardahan", "ARTVIN": "Artvin",
    "AYDIN": "Aydın", "BALIKESIR": "Balıkesir", "BARTIN": "Bartın", "BATMAN": "Batman", "BAYBURT": "Bayburt",
    "BILECIK": "Bilecik", "BINGÖL": "Bingöl", "BITLIS": "Bitlis", "BOLU": "Bolu", "BURDUR": "Burdur",
    "BURSA": "Bursa", "DENIZLI": "Denizli", "DIYARBAKIR": "Diyarbakır", "DÜZCE": "Düzce", "EDIRNE": "Edirne",
    "ELAZIG": "Elazığ", "ERZINCAN": "Erzincan", "ERZURUM": "Erzurum", "ESKISEHIR": "Eskişehir",
    "GAZIANTEP": "Gaziantep", "GIRESUN": "Giresun", "GÜMÜSHANE": "Gümüşhane", "HATAY": "Hatay", "IGDIR": "Iğdır",
    "ISPARTA": "Isparta", "ISTANBUL": "İstanbul", "IZMIR": "İzmir", "IÇEL": "Mersin (İçel)",
    "K.MARAS": "Kahramanmaraş", "KARABÜK": "Karabük", "KARAMAN": "Karaman", "KARS": "Kars",
    "KASTAMONU": "Kastamonu", "KAYSERI": "Kayseri", "KIRKLARELI": "Kırklareli", "KIRSEHIR": "Kırşehir",
    "KOCAELI": "Kocaeli", "KONYA": "Konya", "KÜTAHYA": "Kütahya", "MALATYA": "Malatya", "MANISA": "Manisa",
    "MARDIN": "Mardin", "MUGLA": "Muğla", "MUS": "Muş", "NEVSEHIR": "Nevşehir", "NIGDE": "Niğde", "ORDU": "Ordu",
    "OSMANIYE": "Osmaniye", "RIZE": "Rize", "SAKARYA": "Sakarya", "SAMSUN": "Samsun", "SANLIURFA": "Şanlıurfa",
    "SIIRT": "Siirt", "SINOP": "Sinop", "SIVAS": "Sivas", "TEKIRDAG": "Tekirdağ", "TOKAT": "Tokat",
    "TRABZON": "Trabzon", "TUNCELI": "Tunceli", "USAK": "Uşak", "VAN": "Van", "YALOVA": "Yalova",
    "YOZGAT": "Yozgat", "ZONGULDAK": "Zonguldak", "ÇANAKKALE": "Çanakkale", "ÇANKIRI": "Çankırı",
    "ÇORUM": "Çorum", "UNKNOWN": "Unknown",
}

# --------------------------------------------------------------------------- data dictionary
DATA_DICTIONARY: list[tuple[str, str, str]] = [
    ("InvoiceNo", "raw", "Invoice ID; first three letters are the document series."),
    ("CustomerID", "raw", "B2B customer (store / reseller)."),
    ("InvoiceDate", "raw", "Invoice date (2020-01-02 to 2020-12-31)."),
    ("StockCode", "raw", "Product barcode (EAN/ISBN), stored as text."),
    ("Description", "raw", "Product name (numbers/dates Excel created are converted back to text)."),
    ("Category", "raw", "Detailed product category (306 values, Turkish)."),
    ("City", "raw", "Customer province; missing values set to UNKNOWN."),
    ("Quantity", "raw", "Units on the invoice line."),
    ("NetPrice", "raw", "Net (discounted) unit price paid."),
    ("UnitPrice", "raw", "List unit price."),
    ("Revenue", "derived", "Quantity × NetPrice."),
    ("ListValue", "derived", "Quantity × UnitPrice."),
    ("DiscountPct", "derived", "1 − NetPrice / UnitPrice."),
    ("DocSeries", "derived", "Invoice prefix: BAD, BSR, DPF, DPE or MUH (meaning not documented)."),
    ("MainCategory", "derived", "One of 8 groups built from Category with keyword rules."),
    ("CustomerGroup", "derived", "Key account / Large / Medium / Small by full-year revenue rank (top 10% / next 20% / next 30% / rest)."),
    ("Week", "derived", "Monday of the invoice week."),
    ("Month", "derived", "First day of the invoice month."),
]
