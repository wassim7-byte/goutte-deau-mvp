"""Étape 3 : entraînement et évaluation des modèles.

Découpage temporel : apprentissage avant TEST_START, test après (2024 → 2026).
On compare des modèles légers (pas de deep learning, sobriété énergétique)
à deux références naïves, puis on ré-entraîne le meilleur sur tout l'historique.

Usage : python -m goutte.train
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, brier_score_loss, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from goutte import config
from goutte.features import FEATURES_CLIMATO, FEATURES_METEO, build_dataset, load_days

SEED = 42


def candidates() -> dict:
    return {
        "regression_logistique": make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=1000)
        ),
        "random_forest": make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestClassifier(
                n_estimators=200, max_depth=10, min_samples_leaf=20, n_jobs=-1, random_state=SEED
            ),
        ),
        "gradient_boosting": HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, max_depth=6, random_state=SEED
        ),
    }


def scores(y_true, proba, seuil: float = 0.5) -> dict:
    pred = (proba >= seuil).astype(int)
    return {
        "roc_auc": round(roc_auc_score(y_true, proba), 4),
        "brier": round(brier_score_loss(y_true, proba), 4),
        "accuracy": round(accuracy_score(y_true, pred), 4),
        "precision": round(precision_score(y_true, pred, zero_division=0), 4),
        "rappel": round(recall_score(y_true, pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, pred, zero_division=0), 4),
    }


def main() -> None:
    data = build_dataset(load_days())
    train = data[data["jour"] < config.TEST_START]
    test = data[data["jour"] >= config.TEST_START]
    y_tr, y_te = train["pluie"], test["pluie"]
    print(f"Apprentissage : {len(train)} jours ({train['jour'].min():%Y-%m-%d} → {train['jour'].max():%Y-%m-%d})")
    print(f"Test          : {len(test)} jours ({test['jour'].min():%Y-%m-%d} → {test['jour'].max():%Y-%m-%d})")
    print(f"Taux de jours de pluie (test) : {y_te.mean():.1%}\n")

    results: dict[str, dict] = {}

    # Référence 1 : climatologie (fréquence de pluie par station et par mois, sur l'apprentissage).
    freq = train.groupby([train["station_id"], train["jour"].dt.month])["pluie"].mean()
    p_clim = np.array([freq[(s, m)] for s, m in zip(test["station_id"], test["jour"].dt.month)])
    results["reference_climatologie"] = scores(y_te, p_clim)

    # Référence 2 : persistance (« il pleuvra demain s'il a plu aujourd'hui »).
    p_pers = (test["pluie_mm_j1"].fillna(0) >= config.RAIN_THRESHOLD_MM).astype(float).to_numpy()
    results["reference_persistance"] = scores(y_te, p_pers)

    fitted = {}
    for name, model in candidates().items():
        t0 = time.perf_counter()
        model.fit(train[FEATURES_METEO], y_tr)
        duree = time.perf_counter() - t0
        proba = model.predict_proba(test[FEATURES_METEO])[:, 1]
        results[name] = scores(y_te, proba) | {"duree_entrainement_s": round(duree, 2)}
        fitted[name] = model

    # Modèle climatologique (date + station seulement) pour les dates sans observation de la veille.
    climato = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    climato.fit(train[FEATURES_CLIMATO], y_tr)
    results["climatologie_ml (date seule)"] = scores(y_te, climato.predict_proba(test[FEATURES_CLIMATO])[:, 1])

    table = pd.DataFrame(results).T
    print(table.to_string())

    best = max(fitted, key=lambda n: results[n]["roc_auc"])
    print(f"\nMeilleur modèle (ROC AUC) : {best}")

    # Importance des variables (si le modèle retenu en fournit).
    importances = None
    est = fitted[best][-1] if hasattr(fitted[best], "steps") else fitted[best]
    if hasattr(est, "feature_importances_"):
        importances = (
            pd.Series(est.feature_importances_, index=FEATURES_METEO).sort_values(ascending=False).round(4)
        )
        print("\nVariables les plus importantes :")
        print(importances.head(8).to_string())

    # Ré-entraînement sur tout l'historique pour la mise en service.
    final_meteo = candidates()[best].fit(data[FEATURES_METEO], data["pluie"])
    final_climato = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(
        data[FEATURES_CLIMATO], data["pluie"]
    )

    config.MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(final_meteo, config.MODELS_DIR / "model_meteo.joblib", compress=3)
    joblib.dump(final_climato, config.MODELS_DIR / "model_climato.joblib", compress=3)
    meta = {
        "version": datetime.now(timezone.utc).strftime("%Y%m%d%H%M"),
        "entraine_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "region": config.REGION,
        "modele_meteo": best,
        "seuil_pluie_mm": config.RAIN_THRESHOLD_MM,
        "donnees_jusqu_au": f"{data['jour'].max():%Y-%m-%d}",
        "features_meteo": FEATURES_METEO,
        "features_climato": FEATURES_CLIMATO,
        "evaluation": {
            "periode_test": f"{test['jour'].min():%Y-%m-%d} → {test['jour'].max():%Y-%m-%d}",
            "taux_pluie_test": round(float(y_te.mean()), 4),
            "resultats": results,
        },
        "importances": importances.head(10).to_dict() if importances is not None else None,
    }
    (config.MODELS_DIR / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), "utf-8")
    write_report(meta, table)
    print(f"\nModèles sauvegardés dans {config.MODELS_DIR}")


def write_report(meta: dict, table: pd.DataFrame) -> None:
    config.DOCS_DIR.mkdir(exist_ok=True)
    ev = meta["evaluation"]
    lines = [
        "# Évaluation du modèle",
        "",
        f"*Généré automatiquement par `python -m goutte.train` le {meta['entraine_le']}.*",
        "",
        f"- Région : **{meta['region']}** ({len(config.STATIONS)} stations SYNOP)",
        f"- Cible : jour de pluie = cumul ≥ {meta['seuil_pluie_mm']} mm sur la journée UTC",
        f"- Période de test (jamais vue à l'apprentissage) : {ev['periode_test']}",
        f"- Taux de jours de pluie sur le test : {ev['taux_pluie_test']:.1%}",
        f"- Modèle retenu : **{meta['modele_meteo']}**",
        "",
        "## Résultats",
        "",
        table.fillna("").to_markdown(),
        "",
        "- **ROC AUC** : capacité à classer un jour pluvieux au-dessus d'un jour sec (0,5 = hasard, 1 = parfait).",
        "- **Brier** : erreur quadratique sur la probabilité (plus bas = mieux calibré).",
        "- **Précision / rappel / F1** : calculés au seuil de décision de 50 %.",
        "",
    ]
    if meta["importances"]:
        lines += ["## Variables les plus importantes", "", "| Variable | Importance |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in meta["importances"].items()]
    (config.DOCS_DIR / "evaluation.md").write_text("\n".join(lines) + "\n", "utf-8")


if __name__ == "__main__":
    main()
