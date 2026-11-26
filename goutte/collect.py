"""Étape 1 : collecte des archives SYNOP mensuelles.

Les fichiers sont téléchargés une seule fois (cache local dans data/raw) pour
éviter des transferts réseau inutiles lors des relances.

Usage : python -m goutte.collect
"""
from __future__ import annotations

import time
from datetime import date

import requests

from goutte import config


def download_month(year: int, month: int, session: requests.Session, refresh: bool = False) -> str:
    """Télécharge un mois. Renvoie 'cache', 'ok' ou 'indisponible'."""
    yyyymm = f"{year}{month:02d}"
    target = config.RAW_DIR / f"synop.{yyyymm}.csv.gz"
    if target.exists() and target.stat().st_size > 0 and not refresh:
        return "cache"
    url = config.SYNOP_URL.format(yyyymm=yyyymm)
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    if resp.content[:2] != b"\x1f\x8b":  # pas un gzip : mois pas encore publié
        return "indisponible"
    target.write_bytes(resp.content)
    return "ok"


def main() -> None:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "goutte-deau-mvp/1.0"
    today = date.today()
    n_new = 0
    for year in range(config.START_YEAR, config.END_YEAR + 1):
        for month in range(1, 13):
            if (year, month) > (today.year, today.month):
                break
            # Les deux derniers mois peuvent encore être complétés : on les rafraîchit.
            recent = (today.year * 12 + today.month) - (year * 12 + month) <= 1
            try:
                status = download_month(year, month, session, refresh=recent)
            except requests.RequestException as exc:
                print(f"  ÉCHEC {year}-{month:02d} : {exc}")
                continue
            if status == "ok":
                n_new += 1
                print(f"  téléchargé {year}-{month:02d}")
                time.sleep(0.2)  # politesse envers le serveur
            elif status == "indisponible":
                print(f"  {year}-{month:02d} pas encore publié")
    print(f"Collecte terminée : {n_new} fichier(s) téléchargé(s) dans {config.RAW_DIR}")


if __name__ == "__main__":
    main()
