# 💧 Projet Goutte d'eau : MVP

Prévision du **risque de pluie** pour les agriculteurs, réalisée pour France Météo.
Le MVP couvre une seule région, la **Bretagne** (4 stations SYNOP). Il implémente toute
la chaîne : collecte → nettoyage → base de données → modèle → API → interface.

> Question métier : *« Quelle est la probabilité qu'il tombe au moins 1 mm de pluie tel jour, à telle station ? »*

---

## 1. Architecture

```
 Météo-France open data          goutte/collect.py       goutte/database.py         SQLite
 (archives SYNOP mensuelles) ──► téléchargement    ──►   nettoyage + agrégation ──► data/goutte.db
                                  (cache data/raw)        journalière                  │
                                                                                       ▼
 app/streamlit_app.py  ◄── HTTP/JSON ──  goutte/api.py (FastAPI)  ◄──  goutte/predict.py ◄── models/*.joblib
 (interface agriculteur)                 /prediction, /stations...                        ▲
                                                                       goutte/train.py ───┘
```

| Module | Rôle |
|---|---|
| `goutte/config.py` | Paramètres : région, stations, période, colonnes conservées, seuil de pluie |
| `goutte/collect.py` | Téléchargement des archives SYNOP mensuelles (une seule fois, puis cache) |
| `goutte/database.py` | Nettoyage, contrôle qualité, chargement SQLite, agrégation journalière |
| `goutte/features.py` | Variables explicatives (veille, avant-veille, saison, station) |
| `goutte/train.py` | Entraînement, comparaison des modèles, évaluation, sauvegarde |
| `goutte/predict.py` | Service de prédiction partagé |
| `goutte/api.py` | API REST FastAPI |
| `app/streamlit_app.py` | Interface de démonstration (appelle l'API) |
| `tests/test_api.py` | Tests automatisés de l'API |

## 2. Données

**Source :** archives SYNOP de Météo-France (`donneespubliques.meteofrance.fr`), référencées sur
data.gouv.fr dans la réutilisation *« API de récupération de données météorologiques du réseau
Infoclimat (static) et de Météo-France (SYNOP) »*. Ces archives sont ouvertes et ne demandent
pas de clé, contrairement à l'API Infoclimat, qui exige un jeton.

**Périmètre :** Bretagne, de janvier 2016 à janvier 2026 (dernier mois publié), une mesure toutes les 3 heures.

| Station | Code |
|---|---|
| Brest-Guipavas | 07110 |
| Ploumanac'h | 07117 |
| Rennes-Saint-Jacques | 07130 |
| Belle-Île-Le Talut | 07207 |

**Sobriété des données :** sur les 59 colonnes SYNOP, seules **10** sont conservées : pression,
tendance, température, point de rosée, humidité, vent, nébulosité et pluie sur 3 h.

### Base de données (SQLite, `data/goutte.db`)

- `stations` : référentiel des stations (id, nom, région, coordonnées).
- `observations` : mesures nettoyées toutes les 3 heures. Unités converties en °C et hPa, valeurs aberrantes retirées, les traces (codées -0,1) ramenées à 0.
- `meteo_jour` : agrégats journaliers (cumul de pluie 00 h–24 h UTC, pression moyenne et variation, températures, humidité, vent, nébulosité). Le cumul n'est calculé que si les 8 relevés de la journée sont présents.

## 3. Modèle

- **Cible :** jour de pluie = cumul ≥ 1 mm (définition Météo-France).
- **Variables :** météo de la veille et de l'avant-veille, saison (jour de l'année en sin/cos) et station. Aucune donnée du jour prédit n'est utilisée, donc pas de fuite d'information.
- **Validation temporelle :** apprentissage sur 2016–2023, test sur 2024 → janvier 2026.
- **Modèles comparés :** régression logistique, Random Forest et Gradient Boosting, face à deux références naïves (climatologie et persistance). Aucun deep learning n'est utilisé : chaque entraînement prend moins d'une seconde sur un portable.

| Modèle | ROC AUC ↑ | Brier ↓ | F1 |
|---|---|---|---|
| Référence climatologie | 0,594 | 0,224 | 0,324 |
| Référence persistance | 0,651 | 0,312 | 0,543 |
| Régression logistique | 0,774 | 0,184 | 0,533 |
| **Random Forest (retenu)** | **0,777** | **0,179** | **0,573** |
| Gradient Boosting | 0,765 | 0,185 | 0,569 |

Les variables les plus importantes sont la pluie de la veille, la pression moyenne et la variation
de pression. C'est cohérent avec la météorologie : une baisse de pression annonce l'arrivée d'une perturbation.
Le détail complet est dans [docs/evaluation.md](docs/evaluation.md).

**Deux modes de restitution :**
- `prevision` : les observations de la veille sont dans la base, et le modèle Random Forest est utilisé ;
- `climatologie` : aucune observation n'est disponible pour la veille (date future ou au-delà des données publiées). On renvoie alors la probabilité habituelle de pluie à cette période de l'année (régression logistique sur la date seule).

## 4. API (FastAPI)

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | État du service, version du modèle |
| GET | `/stations` | Liste des stations |
| GET | `/prediction?date=AAAA-MM-JJ&station=07130` | Risque de pluie pour une date et une station |
| GET | `/prediction/region?date=AAAA-MM-JJ` | Risque pour toutes les stations |
| GET | `/modele` | Métadonnées et indicateurs d'évaluation |

Exemple de réponse :

```json
{
  "date": "2026-01-14",
  "station_id": "07110",
  "station": "Brest-Guipavas",
  "probabilite_pluie": 0.72,
  "risque": "élevé",
  "mode": "prevision",
  "explication": "Prévision à partir des observations de la veille (pression, pluie, vent...).",
  "seuil_pluie_mm": 1.0,
  "observe": {"pluie_mm": 5.0, "jour_de_pluie": true},
  "version_modele": "202611260852"
}
```

Niveaux de risque : **faible** (< 30 %), **modéré** (30–60 %), **élevé** (≥ 60 %).
La documentation interactive (Swagger) est disponible sur `http://127.0.0.1:8000/docs`.

## 5. Installation et lancement

Prérequis : Python 3.11 ou plus récent.

```bash
pip install -r requirements.txt

python -m goutte.collect      # 1. télécharge les données (~80 Mo, une seule fois)
python -m goutte.database     # 2. nettoie et charge la base SQLite
python -m goutte.train        # 3. entraîne et évalue (écrit models/ et docs/evaluation.md)

uvicorn goutte.api:app        # 4. API sur http://127.0.0.1:8000
streamlit run app/streamlit_app.py   # 5. interface sur http://localhost:8501 (dans un 2e terminal)

pytest                        # tests
```

Les modèles entraînés sont versionnés dans `models/`, donc l'API peut démarrer sans réentraîner.
Elle a quand même besoin de la base, c'est-à-dire des étapes 1 et 2.

## 6. Indicateurs qualité

| Indicateur | Cible | Valeur actuelle |
|---|---|---|
| ROC AUC sur la période de test | > 0,70 et supérieur aux références | 0,777 ✅ |
| Score de Brier | < référence climatologique (0,224) | 0,179 ✅ |
| Gain d'AUC par rapport à la persistance | > +0,05 | +0,126 ✅ |
| Complétude des journées (cumul calculable) | > 90 % | 94,9 % ✅ |
| Tests automatisés de l'API | 100 % au vert | 6/6 ✅ |
| Temps de réponse de `/prediction` | < 500 ms | < 100 ms en local ✅ |
| Durée d'entraînement | < 1 min sur un poste standard | < 1 s ✅ |

## 7. Documents du projet

- Rapport complet : [docs/Rapport_Goutte_deau_MVP.docx](docs/Rapport_Goutte_deau_MVP.docx) ([PDF](docs/Rapport_Goutte_deau_MVP.pdf))
- Diagrammes : [architecture MVP](docs/architecture/architecture_mvp.png), [architecture cible](docs/architecture/architecture_cible.png), [composants UML](docs/architecture/composants.png). Ils sont générés par `python docs/architecture/generer_diagrammes.py`.

## Planification du projet complet

Méthode, équipe, outils, schéma directeur, Gantt et budget prévisionnel : voir
[docs/planification/planification.md](docs/planification/planification.md) et
[docs/planification/budget_previsionnel.xlsx](docs/planification/budget_previsionnel.xlsx).

## 8. Limites et suite

- Les archives SYNOP publiques s'arrêtent en janvier 2026. En production, il faudra brancher l'API temps réel de Météo-France (portail-api.meteofrance.fr) ou les capteurs IoT du projet pour avoir le mode `prevision` au quotidien.
- Les prévisions sont limitées à J+1 (horizon d'une journée).
- Le modèle repose sur 4 stations. L'étendre à d'autres régions demande seulement de modifier `config.STATIONS`.
