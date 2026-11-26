"""Configuration centrale du MVP Goutte d'eau."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "goutte.db"
MODELS_DIR = ROOT / "models"
DOCS_DIR = ROOT / "docs"

# Source : archives mensuelles SYNOP de Météo-France (open data, sans clé d'API).
# Référencée sur data.gouv.fr (réutilisation « API de récupération de données
# météorologiques du réseau Infoclimat (static) et de Météo-France (SYNOP) »).
SYNOP_URL = (
    "https://donneespubliques.meteofrance.fr/donnees_libres/Txt/Synop/Archive/"
    "synop.{yyyymm}.csv.gz"
)

# Périmètre du MVP : une seule région, la Bretagne (forte activité agricole).
REGION = "Bretagne"
STATIONS = {
    "07110": {"nom": "Brest-Guipavas", "lat": 48.444, "lon": -4.412},
    "07117": {"nom": "Ploumanac'h", "lat": 48.826, "lon": -3.473},
    "07130": {"nom": "Rennes-Saint-Jacques", "lat": 48.069, "lon": -1.734},
    "07207": {"nom": "Belle-Île-Le Talut", "lat": 47.294, "lon": -3.218},
}

# Période collectée (années incluses). Les mois pas encore publiés sont ignorés.
START_YEAR = 2016
END_YEAR = date.today().year

# Colonnes SYNOP réellement utiles au modèle (sobriété : on ne stocke que ça).
SYNOP_COLUMNS = {
    "numer_sta": "station_id",
    "date": "date_utc",
    "pmer": "pmer_pa",     # pression au niveau de la mer (Pa)
    "tend": "tend_pa",     # variation de pression en 3 h (Pa)
    "t": "t_k",            # température (K)
    "td": "td_k",          # point de rosée (K)
    "u": "humidite",       # humidité relative (%)
    "ff": "vent_ms",       # vent moyen 10 min (m/s)
    "n": "nebulosite",     # nébulosité totale (%)
    "rr3": "pluie_3h_mm",  # précipitations des 3 dernières heures (mm)
}

# Seuil agronomique : un « jour de pluie » = cumul >= 1 mm (définition Météo-France).
RAIN_THRESHOLD_MM = 1.0

# Découpage temporel train / test (pas de mélange aléatoire : on prédit le futur).
TEST_START = "2024-01-01"
