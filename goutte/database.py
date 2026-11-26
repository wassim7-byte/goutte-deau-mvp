"""Étape 2 : nettoyage des données SYNOP et chargement dans SQLite.

- filtre sur les stations de la région (Bretagne) ;
- ne conserve que les variables utiles au modèle (sobriété des données) ;
- conversion des unités (K -> °C, Pa -> hPa) et contrôle de plausibilité ;
- agrégation journalière (cumul de pluie, moyennes) dans la table `meteo_jour`.

Usage : python -m goutte.database
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from goutte import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
    station_id TEXT PRIMARY KEY,
    nom        TEXT NOT NULL,
    region     TEXT NOT NULL,
    lat        REAL,
    lon        REAL
);

CREATE TABLE IF NOT EXISTS observations (
    station_id   TEXT NOT NULL REFERENCES stations(station_id),
    date_utc     TEXT NOT NULL,          -- ISO 8601, pas de 3 h
    pmer_hpa     REAL,
    tend_hpa     REAL,
    t_c          REAL,
    td_c         REAL,
    humidite     REAL,
    vent_ms      REAL,
    nebulosite   REAL,
    pluie_3h_mm  REAL,
    PRIMARY KEY (station_id, date_utc)
);

CREATE TABLE IF NOT EXISTS meteo_jour (
    station_id     TEXT NOT NULL REFERENCES stations(station_id),
    jour           TEXT NOT NULL,        -- AAAA-MM-JJ (journée UTC)
    pluie_mm       REAL,                 -- cumul 00h-24h UTC (NULL si incomplet)
    pmer_moy       REAL,
    pmer_var       REAL,                 -- variation de pression sur la journée
    t_moy          REAL,
    t_min          REAL,
    t_max          REAL,
    ecart_rosee    REAL,                 -- t - td moyen (sécheresse de l'air)
    humidite_moy   REAL,
    vent_moy       REAL,
    nebulosite_moy REAL,
    n_obs          INTEGER,
    PRIMARY KEY (station_id, jour)
);
"""

# Bornes de plausibilité physique (valeurs hors bornes -> manquantes).
BOUNDS = {
    "pmer_hpa": (940, 1070),
    "tend_hpa": (-30, 30),
    "t_c": (-30, 45),
    "td_c": (-40, 35),
    "humidite": (0, 100),
    "vent_ms": (0, 70),
    "nebulosite": (0, 100),
    "pluie_3h_mm": (0, 150),
}


def connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def read_raw_file(path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        sep=";",
        usecols=list(config.SYNOP_COLUMNS),
        dtype={"numer_sta": str, "date": str},
        na_values=["mq"],
    )
    return df[df["numer_sta"].isin(config.STATIONS)]


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=config.SYNOP_COLUMNS).copy()
    df["date_utc"] = pd.to_datetime(df["date_utc"], format="%Y%m%d%H%M%S")
    df = df[(df["date_utc"].dt.hour % 3 == 0) & (df["date_utc"].dt.minute == 0)]

    num = [c for c in df.columns if c not in ("station_id", "date_utc")]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")

    # Conversions d'unités.
    df["t_c"] = df.pop("t_k") - 273.15
    df["td_c"] = df.pop("td_k") - 273.15
    df["pmer_hpa"] = df.pop("pmer_pa") / 100
    df["tend_hpa"] = df.pop("tend_pa") / 100
    # En SYNOP, une « trace » de pluie est codée -0.1 : on la ramène à 0.
    df["pluie_3h_mm"] = df["pluie_3h_mm"].clip(lower=0)

    for col, (lo, hi) in BOUNDS.items():
        df.loc[~df[col].between(lo, hi), col] = np.nan

    df = df.drop_duplicates(["station_id", "date_utc"]).sort_values(["station_id", "date_utc"])
    return df[["station_id", "date_utc", *BOUNDS]].round(2)


def daily(obs: pd.DataFrame) -> pd.DataFrame:
    """Agrège les observations tri-horaires en journées UTC."""
    obs = obs.copy()
    obs["jour"] = obs["date_utc"].dt.date
    # rr3 mesuré à H couvre ]H-3h, H] : on le rattache au jour du début de période,
    # ainsi le cumul du jour J = relevés de 03h à 21h de J + relevé de 00h de J+1.
    obs["jour_pluie"] = (obs["date_utc"] - pd.Timedelta(hours=3)).dt.date

    rain = obs.groupby(["station_id", "jour_pluie"])["pluie_3h_mm"].agg(["sum", "count"])
    rain["pluie_mm"] = rain["sum"].where(rain["count"] == 8)  # journée complète exigée
    rain = rain["pluie_mm"].rename_axis(["station_id", "jour"])

    g = obs.groupby(["station_id", "jour"])
    out = pd.DataFrame(
        {
            "pmer_moy": g["pmer_hpa"].mean(),
            "pmer_var": g["pmer_hpa"].last() - g["pmer_hpa"].first(),
            "t_moy": g["t_c"].mean(),
            "t_min": g["t_c"].min(),
            "t_max": g["t_c"].max(),
            "ecart_rosee": (obs["t_c"] - obs["td_c"]).groupby([obs["station_id"], obs["jour"]]).mean(),
            "humidite_moy": g["humidite"].mean(),
            "vent_moy": g["vent_ms"].mean(),
            "nebulosite_moy": g["nebulosite"].mean(),
            "n_obs": g.size(),
        }
    ).join(rain, how="left")
    out = out.reset_index()
    out["jour"] = out["jour"].astype(str)
    cols = ["station_id", "jour", "pluie_mm", *[c for c in out.columns if c not in ("station_id", "jour", "pluie_mm")]]
    return out[cols].round(2)


def build() -> None:
    files = sorted(config.RAW_DIR.glob("synop.*.csv.gz"))
    if not files:
        raise SystemExit("Aucun fichier brut : lancez d'abord `python -m goutte.collect`.")

    raw = pd.concat([read_raw_file(f) for f in files], ignore_index=True)
    obs = clean(raw)
    days = daily(obs)

    with connect() as con:
        con.executescript(
            "DROP TABLE IF EXISTS meteo_jour; DROP TABLE IF EXISTS observations; "
            "DROP TABLE IF EXISTS stations;" + SCHEMA
        )
        con.executemany(
            "INSERT INTO stations VALUES (?, ?, ?, ?, ?)",
            [(sid, s["nom"], config.REGION, s["lat"], s["lon"]) for sid, s in config.STATIONS.items()],
        )
        obs_db = obs.assign(date_utc=obs["date_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
        obs_db.to_sql("observations", con, if_exists="append", index=False)
        days.to_sql("meteo_jour", con, if_exists="append", index=False)
        con.execute("CREATE INDEX IF NOT EXISTS idx_jour ON meteo_jour(jour)")

    print(f"Lignes brutes (région)   : {len(raw):>7}")
    print(f"Observations nettoyées   : {len(obs):>7}")
    print(f"Journées agrégées        : {len(days):>7}")
    print(f"Journées avec cumul pluie: {days['pluie_mm'].notna().sum():>7}")
    print(f"Base : {config.DB_PATH}")


if __name__ == "__main__":
    build()
