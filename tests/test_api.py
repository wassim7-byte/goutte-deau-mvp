"""Tests de l'API (nécessitent la base et les modèles : collect → database → train)."""
from fastapi.testclient import TestClient

from goutte.api import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_stations():
    r = client.get("/stations")
    assert r.status_code == 200
    assert len(r.json()) == 4


def test_prediction_historique_mode_prevision():
    r = client.get("/prediction", params={"date": "2025-01-15", "station": "07130"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "prevision"
    assert 0 <= body["probabilite_pluie"] <= 1
    assert body["risque"] in {"faible", "modéré", "élevé"}
    assert body["observe"] is not None


def test_prediction_future_mode_climatologie():
    from datetime import date, timedelta

    futur = (date.today() + timedelta(days=30)).isoformat()
    r = client.get("/prediction", params={"date": futur})
    assert r.status_code == 200
    assert r.json()["mode"] == "climatologie"
    assert r.json()["observe"] is None


def test_prediction_region():
    r = client.get("/prediction/region", params={"date": "2024-06-01"})
    assert r.status_code == 200
    assert len(r.json()) == 4


def test_erreurs():
    assert client.get("/prediction", params={"date": "2026-01-10", "station": "99999"}).status_code == 404
    assert client.get("/prediction", params={"date": "1990-01-01"}).status_code == 422
    assert client.get("/prediction", params={"date": "pas-une-date"}).status_code == 422
