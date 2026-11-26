"""Étape 4 : API REST de restitution des prévisions (FastAPI).

Lancement : uvicorn goutte.api:app --reload
Documentation interactive : http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from goutte import config
from goutte.predict import metadata, predict

app = FastAPI(
    title="Goutte d'eau – API de risque de pluie",
    description=(
        "MVP France Météo : probabilité qu'il tombe au moins 1 mm de pluie un jour donné, "
        f"pour les stations SYNOP de la région {config.REGION}."
    ),
    version="1.0.0",
)

DATE_MIN = date(config.START_YEAR, 1, 3)


class Observation(BaseModel):
    pluie_mm: float
    jour_de_pluie: bool


class Prediction(BaseModel):
    date: date
    station_id: str
    station: str
    probabilite_pluie: float = Field(ge=0, le=1, description="Probabilité d'un cumul >= 1 mm")
    risque: Literal["faible", "modéré", "élevé"]
    mode: Literal["prevision", "climatologie"]
    explication: str
    seuil_pluie_mm: float
    observe: Observation | None = Field(None, description="Pluie réellement mesurée, si connue")
    version_modele: str


class Station(BaseModel):
    station_id: str
    nom: str
    lat: float
    lon: float


def _check_date(jour: date) -> None:
    date_max = date.today() + timedelta(days=366)
    if not DATE_MIN <= jour <= date_max:
        raise HTTPException(422, f"La date doit être comprise entre {DATE_MIN} et {date_max}.")


@app.get("/health", tags=["Supervision"])
def health() -> dict:
    meta = metadata()
    return {"status": "ok", "version_modele": meta["version"], "donnees_jusqu_au": meta["donnees_jusqu_au"]}


@app.get("/stations", response_model=list[Station], tags=["Référentiel"])
def stations() -> list[Station]:
    return [Station(station_id=k, nom=v["nom"], lat=v["lat"], lon=v["lon"]) for k, v in config.STATIONS.items()]


@app.get("/prediction", response_model=Prediction, tags=["Prévision"])
def prediction(
    date: date = Query(..., description="Date au format AAAA-MM-JJ", examples=["2026-01-10"]),
    station: str = Query("07130", description="Identifiant de la station SYNOP"),
) -> Prediction:
    """Risque de pluie pour une date et une station."""
    _check_date(date)
    if station not in config.STATIONS:
        raise HTTPException(404, f"Station inconnue : {station}. Voir /stations.")
    return Prediction(**predict(date, station))


@app.get("/prediction/region", response_model=list[Prediction], tags=["Prévision"])
def prediction_region(date: date = Query(..., description="Date au format AAAA-MM-JJ")) -> list[Prediction]:
    """Risque de pluie pour une date, sur toutes les stations de la région."""
    _check_date(date)
    return [Prediction(**predict(date, sid)) for sid in config.STATIONS]


@app.get("/modele", tags=["Supervision"])
def modele() -> dict:
    """Métadonnées et indicateurs d'évaluation du modèle en service."""
    return metadata()
