"""Service de prédiction : charge les modèles et calcule le risque de pluie d'une date."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from functools import lru_cache

import joblib
import pandas as pd

from goutte import config
from goutte.features import (
    FEATURES_CLIMATO, FEATURES_METEO, VEILLE_COLS, season, station_dummies,
)

# Seuils de restitution pour l'agriculteur.
NIVEAUX = [(0.6, "élevé"), (0.3, "modéré"), (0.0, "faible")]


@lru_cache
def models():
    return (
        joblib.load(config.MODELS_DIR / "model_meteo.joblib"),
        joblib.load(config.MODELS_DIR / "model_climato.joblib"),
    )


@lru_cache
def metadata() -> dict:
    return json.loads((config.MODELS_DIR / "metadata.json").read_text("utf-8"))


def niveau(p: float) -> str:
    return next(label for seuil, label in NIVEAUX if p >= seuil)


def _day(con: sqlite3.Connection, station: str, jour: date) -> dict | None:
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT * FROM meteo_jour WHERE station_id = ? AND jour = ?", (station, jour.isoformat())
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["amplitude_t"] = (
        d["t_max"] - d["t_min"] if d["t_max"] is not None and d["t_min"] is not None else None
    )
    return d


def predict(jour: date, station: str) -> dict:
    if station not in config.STATIONS:
        raise KeyError(station)
    model_meteo, model_climato = models()

    with sqlite3.connect(config.DB_PATH) as con:
        j1 = _day(con, station, jour - timedelta(days=1))
        j2 = _day(con, station, jour - timedelta(days=2))
        j0 = _day(con, station, jour)

    base = pd.concat(
        [season(pd.Series([pd.Timestamp(jour)])), station_dummies(pd.Series([station]))], axis=1
    )
    if j1 is not None:
        for c in VEILLE_COLS:
            base[f"{c}_j1"] = j1.get(c)
        base["pluie_mm_j2"] = j2.get("pluie_mm") if j2 else None
        base["pmer_moy_j2"] = j2.get("pmer_moy") if j2 else None
        x = base[FEATURES_METEO].astype(float)
        proba = float(model_meteo.predict_proba(x)[0, 1])
        mode = "prevision"
        explication = "Prévision à partir des observations de la veille (pression, pluie, vent...)."
    else:
        proba = float(model_climato.predict_proba(base[FEATURES_CLIMATO].astype(float))[0, 1])
        mode = "climatologie"
        explication = (
            "Pas d'observation disponible pour la veille : probabilité climatologique "
            "(fréquence habituelle de pluie à cette période de l'année)."
        )

    observe = None
    if j0 is not None and j0.get("pluie_mm") is not None:
        observe = {
            "pluie_mm": j0["pluie_mm"],
            "jour_de_pluie": j0["pluie_mm"] >= config.RAIN_THRESHOLD_MM,
        }

    return {
        "date": jour.isoformat(),
        "station_id": station,
        "station": config.STATIONS[station]["nom"],
        "probabilite_pluie": round(proba, 3),
        "risque": niveau(proba),
        "mode": mode,
        "explication": explication,
        "seuil_pluie_mm": config.RAIN_THRESHOLD_MM,
        "observe": observe,
        "version_modele": metadata()["version"],
    }
