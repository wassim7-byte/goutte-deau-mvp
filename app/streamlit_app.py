"""Interface de démonstration Goutte d'eau (Streamlit).

L'interface ne charge pas le modèle : elle interroge l'API FastAPI, ce qui
prouve le fonctionnement de toute la chaîne (base -> modèle -> API -> UI).

Lancement : streamlit run app/streamlit_app.py   (l'API doit tourner)
"""
from __future__ import annotations

import os
from datetime import date

import pandas as pd
import requests
import streamlit as st

API_URL = os.environ.get("GOUTTE_API_URL", "http://127.0.0.1:8000")

# Le niveau de risque est toujours indiqué par un texte ET un symbole,
# jamais par la seule couleur (règle d'accessibilité RGAA / WCAG 1.4.1).
SYMBOLES = {"faible": "☀️ Risque faible", "modéré": "⛅ Risque modéré", "élevé": "🌧️ Risque élevé"}

st.set_page_config(page_title="Goutte d'eau – Risque de pluie", page_icon="💧", layout="centered")


@st.cache_data(ttl=300)
def api_get(path: str, **params):
    r = requests.get(f"{API_URL}{path}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


st.title("💧 Goutte d'eau")
st.write(
    "Estimation du **risque de pluie** (au moins 1 mm dans la journée) pour les "
    "agriculteurs de Bretagne. Prototype (MVP) France Météo."
)

try:
    health = api_get("/health")
    stations = api_get("/stations")
except requests.RequestException:
    st.error(
        f"L'API ne répond pas à l'adresse {API_URL}. "
        "Lancez-la avec : `uvicorn goutte.api:app`."
    )
    st.stop()

noms = {s["station_id"]: s["nom"] for s in stations}

# Lien partageable : ?date=AAAA-MM-JJ&station=07130 (ou station=region) lance directement l'estimation.
qp = st.query_params
try:
    date_defaut = date.fromisoformat(qp.get("date", health["donnees_jusqu_au"]))
except ValueError:
    date_defaut = date.fromisoformat(health["donnees_jusqu_au"])
options = ["region", *noms]
station_defaut = qp.get("station", "region")
index_defaut = options.index(station_defaut) if station_defaut in options else 0

with st.form("recherche"):
    col1, col2 = st.columns(2)
    jour = col1.date_input(
        "Date",
        value=date_defaut,
        min_value=date(2016, 1, 3),
        help="Format JJ/MM/AAAA",
        format="DD/MM/YYYY",
    )
    choix = col2.selectbox(
        "Station météo",
        options=options,
        index=index_defaut,
        format_func=lambda k: "Toute la région" if k == "region" else noms[k],
    )
    envoyer = st.form_submit_button("Estimer le risque de pluie", type="primary")
    envoyer = envoyer or "date" in qp

st.caption(
    f"Observations disponibles jusqu'au {date.fromisoformat(health['donnees_jusqu_au']):%d/%m/%Y}. "
    "Au-delà, l'estimation repose sur la climatologie (fréquence habituelle de pluie)."
)

if envoyer:
    try:
        if choix == "region":
            res = api_get("/prediction/region", date=jour.isoformat())
        else:
            res = [api_get("/prediction", date=jour.isoformat(), station=choix)]
    except requests.RequestException as exc:
        st.error(f"Erreur lors de l'appel à l'API : {exc}")
        st.stop()

    st.subheader(f"Résultat pour le {jour:%d/%m/%Y}")
    if len(res) == 1:
        p = res[0]
        c1, c2 = st.columns(2)
        c1.metric("Probabilité de pluie", f"{p['probabilite_pluie']:.0%}")
        c2.metric("Niveau", SYMBOLES[p["risque"]])
        if p["observe"]:
            verdict = "jour de pluie" if p["observe"]["jour_de_pluie"] else "jour sec"
            st.info(f"Mesure réelle à {p['station']} : {p['observe']['pluie_mm']} mm ({verdict}).")
    else:
        df = pd.DataFrame(
            {
                "Station": [p["station"] for p in res],
                "Probabilité": [f"{p['probabilite_pluie']:.0%}" for p in res],
                "Niveau": [SYMBOLES[p["risque"]] for p in res],
                "Pluie mesurée (mm)": [f"{p['observe']['pluie_mm']:.1f}" if p["observe"] else "—" for p in res],
            }
        )
        st.table(df.set_index("Station"))
        st.bar_chart(
            pd.DataFrame({"Probabilité de pluie (%)": [round(100 * p["probabilite_pluie"]) for p in res]},
                         index=[p["station"] for p in res]),
            y_label="Probabilité (%)",
        )
    st.write(f"**Méthode :** {res[0]['explication']}")

with st.expander("Indicateurs qualité du modèle", expanded=qp.get("qualite") == "1"):
    meta = api_get("/modele")
    ev = meta["evaluation"]
    st.write(
        f"Modèle en service : **{meta['modele_meteo']}** (version {meta['version']}). "
        f"Évalué sur des jours jamais vus à l'apprentissage ({ev['periode_test']})."
    )
    tableau = pd.DataFrame(ev["resultats"]).T[["roc_auc", "brier", "precision", "rappel", "f1"]]
    tableau.columns = ["ROC AUC (↑)", "Brier (↓)", "Précision", "Rappel", "F1"]
    st.table(tableau.style.format("{:.3f}"))
    st.caption(
        "ROC AUC : 0,5 = hasard, 1 = parfait. Brier : erreur sur la probabilité (plus bas = mieux). "
        "Les deux « références » sont des prévisions naïves que le modèle doit battre."
    )
