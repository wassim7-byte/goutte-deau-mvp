"""Construction des variables explicatives.

Cible : `pluie` = 1 si le cumul du jour J atteint RAIN_THRESHOLD_MM (1 mm).
Variables : météo observée la veille (J-1) et l'avant-veille (J-2) à la même
station, saisonnalité (jour de l'année encodé en sin/cos) et station.
Aucune donnée du jour J n'est utilisée : pas de fuite d'information.
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from goutte import config

VEILLE_COLS = [
    "pluie_mm", "pmer_moy", "pmer_var", "t_moy", "amplitude_t",
    "ecart_rosee", "humidite_moy", "vent_moy", "nebulosite_moy",
]
STATION_COLS = [f"station_{sid}" for sid in config.STATIONS]
SAISON_COLS = ["doy_sin", "doy_cos"]

# Modèle « prévision » : saison + station + météo de J-1 et J-2.
FEATURES_METEO = (
    SAISON_COLS + STATION_COLS
    + [f"{c}_j1" for c in VEILLE_COLS]
    + ["pluie_mm_j2", "pmer_moy_j2"]
)
# Modèle « climatologie » : uniquement la date et la station.
FEATURES_CLIMATO = SAISON_COLS + STATION_COLS


def load_days(con: sqlite3.Connection | None = None) -> pd.DataFrame:
    own = con is None
    con = con or sqlite3.connect(config.DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM meteo_jour", con, dtype={"station_id": str})
    finally:
        if own:
            con.close()
    df["jour"] = pd.to_datetime(df["jour"])
    df["amplitude_t"] = df["t_max"] - df["t_min"]
    return df


def season(jours: pd.Series) -> pd.DataFrame:
    doy = jours.dt.dayofyear
    return pd.DataFrame(
        {"doy_sin": np.sin(2 * np.pi * doy / 365.25), "doy_cos": np.cos(2 * np.pi * doy / 365.25)},
        index=jours.index,
    )


def station_dummies(stations: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {f"station_{sid}": (stations == sid).astype(int) for sid in config.STATIONS},
        index=stations.index,
    )


def build_dataset(days: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par (station, jour J) avec les variables de J-1 / J-2 et la cible."""
    d = days.set_index(["station_id", "jour"]).sort_index()
    rows = d[["pluie_mm"]].rename(columns={"pluie_mm": "pluie_mm_j0"}).reset_index()

    def lagged(n: int, cols: list[str], suffix: str) -> pd.DataFrame:
        lag = d[cols].reset_index()
        lag["jour"] = lag["jour"] + pd.Timedelta(days=n)  # la valeur de J-n est rattachée à J
        return lag.rename(columns={c: f"{c}{suffix}" for c in cols})

    rows = rows.merge(lagged(1, VEILLE_COLS, "_j1"), on=["station_id", "jour"], how="left")
    rows = rows.merge(lagged(2, ["pluie_mm", "pmer_moy"], "_j2"), on=["station_id", "jour"], how="left")
    rows = pd.concat([rows, season(rows["jour"]), station_dummies(rows["station_id"])], axis=1)
    rows["pluie"] = (rows["pluie_mm_j0"] >= config.RAIN_THRESHOLD_MM).astype(int)
    return rows[rows["pluie_mm_j0"].notna()].reset_index(drop=True)
