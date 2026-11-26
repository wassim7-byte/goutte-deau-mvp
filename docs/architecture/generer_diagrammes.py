"""Génère les diagrammes d'architecture (MVP et cible) et de composants (UML).

Usage : python docs/architecture/generer_diagrammes.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Wedge

OUT = Path(__file__).resolve().parent

INK = "#1F2937"
MUTED = "#6B7280"
C = {
    "source": ("#FEF3C7", "#B45309"),
    "ingest": ("#DBEAFE", "#1D4ED8"),
    "store": ("#E0E7FF", "#4338CA"),
    "ml": ("#EDE9FE", "#6D28D9"),
    "api": ("#D1FAE5", "#047857"),
    "user": ("#FCE7F3", "#BE185D"),
    "cross": ("#F3F4F6", "#4B5563"),
}


def new(w: float, h: float, title: str, subtitle: str = ""):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w * 10)
    ax.set_ylim(0, h * 10)
    ax.axis("off")
    ax.text(2, h * 10 - 3, title, fontsize=15, fontweight="bold", color=INK, va="top")
    if subtitle:
        ax.text(2, h * 10 - 7.5, subtitle, fontsize=9.5, color=MUTED, va="top")
    return fig, ax


def box(ax, x, y, w, h, title, lines=(), kind="ingest", title_size=10, line_size=8, stereo=None):
    fill, edge = C[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
                                fc=fill, ec=edge, lw=1.4))
    ty = y + h - 2.2
    if stereo:
        ax.text(x + w / 2, ty, f"«{stereo}»", ha="center", va="top", fontsize=7.5, color=edge, style="italic")
        ty -= 2.6
    ax.text(x + w / 2, ty, title, ha="center", va="top", fontsize=title_size, fontweight="bold", color=edge)
    for i, line in enumerate(lines):
        ax.text(x + w / 2, ty - 3.4 - i * 2.7, line, ha="center", va="top", fontsize=line_size, color=INK)
    return (x, y, w, h)


def lane(ax, x, y, w, h, label, kind):
    fill, edge = C[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.5",
                                fc="white", ec=edge, lw=1, ls=(0, (4, 3)), alpha=0.9))
    ax.text(x + w / 2, y + h - 1.6, label.upper(), ha="center", va="top", fontsize=8.5,
            fontweight="bold", color=edge)


def arrow(ax, p, q, label="", dashed=False, color=INK, rad=0.0, lpos=0.5, loff=(0, 1.4), size=7.5):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=13, lw=1.3, color=color,
                                 ls=(0, (5, 3)) if dashed else "-", connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=2, shrinkB=2))
    if label:
        mx = p[0] + (q[0] - p[0]) * lpos + loff[0]
        my = p[1] + (q[1] - p[1]) * lpos + loff[1]
        ax.text(mx, my, label, ha="center", va="bottom", fontsize=size, color=color,
                bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9))


def right(b, dy=0.5):
    return (b[0] + b[2] + 0.4, b[1] + b[3] * dy)


def left(b, dy=0.5):
    return (b[0] - 0.4, b[1] + b[3] * dy)


def top(b, dx=0.5):
    return (b[0] + b[2] * dx, b[1] + b[3] + 0.4)


def bottom(b, dx=0.5):
    return (b[0] + b[2] * dx, b[1] - 0.4)


def legend(ax, x, y):
    ax.add_patch(FancyArrowPatch((x, y), (x + 8, y), arrowstyle="-|>", mutation_scale=12, lw=1.3, color=INK))
    ax.text(x + 9.5, y, "flux en ligne (requête utilisateur)", va="center", fontsize=8, color=INK)
    ax.add_patch(FancyArrowPatch((x + 52, y), (x + 60, y), arrowstyle="-|>", mutation_scale=12, lw=1.3,
                                 color=INK, ls=(0, (5, 3))))
    ax.text(x + 61.5, y, "traitement par lot (batch, planifié)", va="center", fontsize=8, color=INK)


# ----------------------------------------------------------------------------- MVP
def architecture_mvp() -> None:
    fig, ax = new(17, 9.4, "Architecture du MVP Goutte d'eau",
                  "Région Bretagne – Python 3, SQLite, scikit-learn, FastAPI, Streamlit – exécution sur un seul serveur")
    # couloirs
    lane(ax, 2, 10, 26, 68, "Source externe", "source")
    lane(ax, 31, 10, 40, 68, "Ingestion et stockage", "ingest")
    lane(ax, 74, 10, 32, 68, "Intelligence (ML)", "ml")
    lane(ax, 109, 10, 30, 68, "Exposition", "api")
    lane(ax, 142, 10, 26, 68, "Utilisateurs", "user")

    src = box(ax, 4.5, 40, 21, 22, "Météo-France", ["Open data SYNOP", "archives mensuelles", "CSV.gz via HTTPS", "licence Etalab"], "source")
    col = box(ax, 34, 55, 34, 15, "Collecteur", ["goutte/collect.py", "téléchargement + cache data/raw"], "ingest")
    etl = box(ax, 34, 35, 34, 15, "ETL", ["goutte/database.py", "nettoyage, contrôle qualité,", "agrégation journalière"], "ingest")
    db = box(ax, 34, 13, 34, 17, "Base SQLite", ["data/goutte.db", "stations · observations", "meteo_jour"], "store")
    tr = box(ax, 77, 55, 26, 15, "Entraînement", ["goutte/train.py", "Random Forest, évaluation"], "ml")
    art = box(ax, 77, 35, 26, 15, "Artefacts modèle", ["models/*.joblib", "metadata.json"], "store")
    pred = box(ax, 77, 13, 26, 17, "Service de prédiction", ["goutte/predict.py", "mode prévision /", "climatologie"], "ml")
    api = box(ax, 112, 35, 24, 27, "API REST FastAPI", ["goutte/api.py", "GET /prediction", "GET /prediction/region", "GET /stations", "GET /health · /modele", "Swagger /docs"], "api")
    ui = box(ax, 145, 47, 20, 17, "Interface Streamlit", ["app/streamlit_app.py", "formulaire date", "+ station"], "user")
    usr = box(ax, 145, 20, 20, 17, "Agriculteur", ["navigateur web", "(ordinateur ou", "mobile)"], "user")

    arrow(ax, right(src, 0.85), left(col, 0.6), "", dashed=True)
    ax.text(29.5, 66.5, "HTTPS\n(mensuel)", ha="center", va="bottom", fontsize=7.5, color=INK)
    arrow(ax, bottom(col), top(etl), "fichiers bruts", dashed=True, loff=(6.5, -1))
    arrow(ax, bottom(etl), top(db), "données nettoyées", dashed=True, loff=(8, -1))
    arrow(ax, right(db, 0.85), left(tr, 0.15), "", dashed=True)
    ax.text(72.5, 40, "historique\n2016–2026", ha="center", va="center", fontsize=7.3, color=INK,
            rotation=73, bbox=dict(fc="white", ec="none", pad=0.4))
    arrow(ax, bottom(tr), top(art), "sérialisation", dashed=True, loff=(6, -1))
    arrow(ax, bottom(art), top(pred), "chargement", loff=(5.5, -1))
    arrow(ax, right(db, 0.35), left(pred, 0.35), "météo J-1, J-2", loff=(0, 0.6))
    arrow(ax, right(pred, 0.6), left(api, 0.15), "probabilité", lpos=0.5, loff=(0, 0.8))
    arrow(ax, left(ui, 0.6), right(api, 0.8), "HTTP / JSON", lpos=0.5, loff=(0, 0.8))
    arrow(ax, top(usr), bottom(ui), "utilise", loff=(4, -1))
    legend(ax, 3, 4)
    fig.savefig(OUT / "architecture_mvp.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- cible
def architecture_cible() -> None:
    fig, ax = new(17, 10.6, "Architecture cible (projet complet, national)",
                  "Hébergement cloud français bas carbone – conteneurs orchestrés – sécurité et observabilité transverses")
    lane(ax, 2, 24, 26, 66, "Sources", "source")
    lane(ax, 31, 24, 36, 66, "Ingestion et stockage", "ingest")
    lane(ax, 70, 24, 34, 66, "Intelligence (MLOps)", "ml")
    lane(ax, 107, 24, 30, 66, "Exposition", "api")
    lane(ax, 140, 24, 28, 66, "Utilisateurs", "user")

    mf = box(ax, 4.5, 70, 21, 14, "API Météo-France", ["observations", "temps réel"], "source")
    iot = box(ax, 4.5, 50, 21, 15, "Capteurs IoT", ["pluie, T°, humidité,", "pression (LoRaWAN)"], "source")
    ic = box(ax, 4.5, 29, 21, 15, "Infoclimat", ["source de secours"], "source")
    orch = box(ax, 34, 70, 30, 14, "Orchestrateur", ["Airflow / cron", "collecte horaire"], "ingest")
    mqtt = box(ax, 34, 50, 30, 15, "Broker MQTT", ["réception des mesures IoT", "contrôle qualité"], "ingest")
    pg = box(ax, 34, 29, 30, 15, "PostgreSQL + TimescaleDB", ["séries temporelles", "réplication, sauvegardes"], "store")
    trn = box(ax, 73, 70, 28, 14, "Pipeline d'entraînement", ["réentraînement mensuel", "modèles par région"], "ml")
    reg = box(ax, 73, 50, 28, 15, "Registre MLflow", ["versions de modèles", "métriques, traçabilité"], "store")
    mon = box(ax, 73, 29, 28, 15, "Suivi de dérive", ["performances réelles", "vs prévues → alerte"], "ml")
    gw = box(ax, 110, 70, 24, 14, "API Gateway", ["HTTPS, clés d'API,", "quotas, cache"], "api")
    apis = box(ax, 110, 46, 24, 19, "API FastAPI", ["conteneurs", "(mise à l'échelle", "horizontale)"], "api")
    alert = box(ax, 110, 29, 24, 13, "Service d'alertes", ["SMS / notifications"], "api")
    web = box(ax, 143, 70, 22, 14, "Application web", ["responsive,", "conforme RGAA"], "user")
    part = box(ax, 143, 50, 22, 15, "Partenaires", ["coopératives, outils", "agricoles (API)"], "user")
    farm = box(ax, 143, 29, 22, 15, "Agriculteurs", ["via l'application web", "et les alertes SMS"], "user")

    arrow(ax, right(mf), left(orch), "HTTPS", dashed=True)
    arrow(ax, right(iot), left(mqtt), "MQTT/TLS")
    arrow(ax, right(ic, 0.85), left(orch, 0.1), "", dashed=True)
    ax.text(29.6, 47, "secours", ha="center", va="center", fontsize=7.3, color=INK, rotation=77,
            bbox=dict(fc="white", ec="none", pad=0.4))
    arrow(ax, bottom(orch, 0.25), top(pg, 0.25), "", dashed=True, rad=0.0)
    arrow(ax, bottom(mqtt, 0.7), top(pg, 0.7), "")
    arrow(ax, right(pg, 0.85), left(trn, 0.2), "historique", dashed=True, lpos=0.5, loff=(0, 0.5))
    arrow(ax, bottom(trn), top(reg), "publie", dashed=True, loff=(4.5, -1))
    arrow(ax, right(reg, 0.6), left(apis, 0.6), "")
    ax.text(105.5, 60.5, "déploie", ha="center", va="bottom", fontsize=7.3, color=INK,
            bbox=dict(fc="white", ec="none", pad=0.4))
    arrow(ax, right(pg, 0.3), left(mon, 0.3), "mesures réelles", dashed=True, lpos=0.5, loff=(0, 0.5))
    arrow(ax, top(mon), bottom(reg), "dégradation", dashed=True, loff=(5, -1))
    arrow(ax, bottom(gw), top(apis), "", loff=(0, 0))
    arrow(ax, bottom(apis), top(alert), "risque élevé", loff=(5.5, -1))
    arrow(ax, left(web), right(gw), "HTTPS/JSON")
    arrow(ax, left(part, 0.7), right(gw, 0.2), "")
    ax.text(138.5, 63, "API", ha="center", fontsize=7.3, color=INK)
    arrow(ax, right(alert, 0.5), left(farm, 0.5), "SMS", lpos=0.5, loff=(0, 0.5))

    # transverses
    cross = [
        (2, "Sécurité", "TLS partout, IAM, secrets chiffrés, journalisation, RGPD"),
        (58, "Observabilité", "Prometheus / Grafana, alertes d'exploitation"),
        (114, "Hébergement", "cloud français bas carbone, Kubernetes, CI/CD GitHub Actions"),
    ]
    for x, t, d in cross:
        box(ax, x, 9, 52, 10, t, [d], "cross", title_size=9.5, line_size=7.6)
    legend(ax, 3, 3.5)
    fig.savefig(OUT / "architecture_cible.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------- composants
def provided(ax, x, y, label, side="right", color=INK):
    """Interface fournie (« lollipop ») : trait + cercle."""
    dx = 4 if side == "right" else -4
    ax.plot([x, x + dx], [y, y], color=color, lw=1.2)
    ax.add_patch(Circle((x + dx + (1.1 if side == "right" else -1.1), y), 1.1, fc="white", ec=color, lw=1.2))
    ha = "left" if side == "right" else "right"
    ax.text(x + dx + (2.8 if side == "right" else -2.8), y, label, va="center", ha=ha, fontsize=7.5,
            color=color, style="italic")
    return (x + dx + (2.2 if side == "right" else -2.2), y)


def required(ax, x, y, side="left", color=INK):
    """Interface requise (« socket ») : trait + demi-cercle."""
    dx = -4 if side == "left" else 4
    ax.plot([x, x + dx], [y, y], color=color, lw=1.2)
    cx = x + dx + (-1.5 if side == "left" else 1.5)
    theta = (270, 90) if side == "left" else (90, 270)
    ax.add_patch(Wedge((cx, y), 1.6, *theta, width=0.01, fc="none", ec=color, lw=1.2))
    return (cx - (1.6 if side == "left" else -1.6), y)


def assembly(ax, x_prov, x_req, y, label):
    """Connecteur d'assemblage UML : boule (fournie) emboîtée dans une douille (requise)."""
    cx = (x_prov + x_req) / 2
    ax.plot([x_prov, cx - 1.1], [y, y], color=INK, lw=1.2)
    ax.add_patch(Circle((cx, y), 1.1, fc="white", ec=INK, lw=1.2, zorder=3))
    ax.add_patch(Wedge((cx, y), 1.8, -90, 90, width=0.01, fc="none", ec=INK, lw=1.2, zorder=3))
    ax.plot([cx + 1.8, x_req], [y, y], color=INK, lw=1.2)
    ax.text(cx, y + 2.6, label, ha="center", va="bottom", fontsize=7.5, color=INK, style="italic")


def component(ax, x, y, w, h, name, module, lines=(), kind="ingest", icon=True):
    b = box(ax, x, y, w, h, name, (module, *lines), kind, title_size=9.5, line_size=7.6, stereo="component")
    if not icon:
        return b
    # icône UML de composant
    fill, edge = C[kind]
    ix, iy = x + w - 4.2, y + h - 4.2
    ax.add_patch(FancyBboxPatch((ix, iy), 3, 3, boxstyle="square,pad=0", fc="white", ec=edge, lw=0.9))
    for k in (0.5, 1.7):
        ax.add_patch(FancyBboxPatch((ix - 0.6, iy + k), 1.2, 0.7, boxstyle="square,pad=0", fc="white", ec=edge, lw=0.9))
    return b


def composants() -> None:
    fig, ax = new(17, 10.2, "Diagramme de composants (UML) – MVP Goutte d'eau",
                  "Chaque composant est un module Python du dépôt ; ○ interface fournie, ◖ interface requise, ⇢ dépendance")

    ext = box(ax, 2, 62, 22, 16, "Météo-France", ["serveur open data", "HTTPS"], "source", stereo="external")
    colc = component(ax, 34, 62, 26, 18, "Collecteur", "goutte.collect", ["download_month()"], "ingest")
    etlc = component(ax, 34, 34, 26, 20, "ETL / Base", "goutte.database", ["clean(), daily()", "build()"], "ingest")
    dbn = box(ax, 34, 9, 26, 15, "goutte.db", ["SQLite : stations,", "observations, meteo_jour"], "store", stereo="artifact")
    feat = component(ax, 75, 62, 28, 18, "Features", "goutte.features", ["build_dataset()", "season(), station_dummies()"], "ml")
    trc = component(ax, 75, 34, 28, 20, "Entraînement", "goutte.train", ["candidates(), scores()", "main()"], "ml")
    mdl = box(ax, 75, 9, 28, 15, "models/", ["model_meteo.joblib", "model_climato.joblib, metadata.json"], "store", stereo="artifact")
    prc = component(ax, 118, 34, 26, 20, "Prédiction", "goutte.predict", ["predict(date, station)", "metadata()"], "ml")
    apic = component(ax, 113, 58, 30, 24, "API REST", "goutte.api", ["FastAPI + Pydantic", "/prediction, /prediction/region", "/stations, /health, /modele"], "api")
    uic = component(ax, 151, 61, 18, 18, "Interface", "app.streamlit", ["Streamlit"], "user", icon=False)
    cfg = component(ax, 2, 30, 22, 22, "Configuration", "goutte.config", ["région, stations,", "chemins, seuils"], "cross")

    # Connecteurs d'assemblage (interface fournie <-> requise)
    assembly(ax, ext[0] + ext[2] + 0.4, colc[0] - 0.4, 70, "HTTP SYNOP")
    assembly(ax, apic[0] + apic[2] + 0.4, uic[0] - 0.4, 70, "REST/JSON")
    # Collecteur -> fichiers bruts -> ETL
    arrow(ax, bottom(colc), top(etlc), "fichiers data/raw", dashed=True, loff=(7, -1))
    arrow(ax, bottom(etlc), top(dbn), "écrit", dashed=True, loff=(3.5, -1))
    # Features lit la base
    arrow(ax, right(dbn, 0.85), left(feat, 0.15), "", dashed=True)
    ax.text(67.5, 45, "lit meteo_jour", ha="center", va="center", fontsize=7.3, color=INK, rotation=72,
            bbox=dict(fc="white", ec="none", pad=0.4))
    arrow(ax, bottom(feat), top(trc), "IDataset", dashed=True, loff=(4.5, -1))
    arrow(ax, bottom(trc), top(mdl), "sérialise", dashed=True, loff=(4.5, -1))
    # Prédiction dépend des modèles et des fonctions de features
    arrow(ax, right(mdl, 0.7), left(prc, 0.25), "charge", dashed=True, lpos=0.5, loff=(0, 0.5))
    arrow(ax, right(feat, 0.2), left(prc, 0.75), "season(), dummies()", dashed=True, lpos=0.5, loff=(0, 0.5))
    # API requiert IPrediction
    arrow(ax, top(prc), bottom(apic, 0.4), "IPrediction : predict()", loff=(9, -1.5))
    # config utilisée par tous
    for target in (colc, etlc):
        arrow(ax, right(cfg, 0.5), left(target, 0.3), "", dashed=True, color=MUTED)
    ax.text(13, 27, "utilisée par tous les modules", ha="center", fontsize=7.2, color=MUTED, style="italic")
    fig.savefig(OUT / "composants.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    architecture_mvp()
    architecture_cible()
    composants()
    print("Diagrammes générés dans", OUT)
