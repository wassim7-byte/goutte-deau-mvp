"""Génère le planning (Gantt PNG) et le budget prévisionnel (Excel avec formules).

Une seule source de vérité : les listes ROLES / TACHES / AUTRES_COUTS ci-dessous.
Usage : python docs/planification/generer_planification.py
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT = Path(__file__).resolve().parent
DEBUT = date(2027, 1, 4)  # lundi de la semaine 1
JOURS_SEMAINE = 5
CONTINGENCE = 0.10

# (code, rôle, TJM chargé en € HT) : ordres de grandeur du marché français 2026
# (coût interne chargé ou prestataire en régie).
ROLES = [
    ("CP", "Chef de projet / Scrum Master", 700),
    ("PO", "Product Owner (métier France Météo)", 550),
    ("DS", "Data Scientist", 600),
    ("DE", "Data Engineer", 600),
    ("BE", "Développeur back-end", 550),
    ("FE", "Développeur front / UX-UI", 550),
    ("OPS", "Ingénieur DevOps / MLOps", 650),
    ("IOT", "Ingénieur IoT", 600),
    ("QA", "Testeur QA / accessibilité", 500),
    ("MET", "Expert prévisionniste", 500),
]
CODES = [r[0] for r in ROLES]

# (phase, tâche, semaine de début (0 = S1), durée en semaines, {rôle: ETP})
TACHES = [
    ("0. Cadrage", "Finalisation du cahier des charges et du backlog", 0, 3, {"CP": 1, "PO": 1, "DS": 0.5, "MET": 0.5}),
    ("0. Cadrage", "Outils collaboratifs (GitHub, Jira, Teams), RGPD, risques", 1, 2, {"CP": 0.5, "OPS": 0.5}),
    ("1. MVP Bretagne", "Sprint 1 : collecte des données et base SQLite", 3, 2, {"CP": 0.5, "PO": 0.2, "DS": 1, "DE": 1}),
    ("1. MVP Bretagne", "Sprint 2 : modèle de ML et évaluation", 5, 2, {"CP": 0.5, "PO": 0.2, "DS": 1, "DE": 0.5, "MET": 0.3}),
    ("1. MVP Bretagne", "Sprint 3 : API FastAPI et tests", 7, 2, {"CP": 0.5, "PO": 0.2, "DS": 0.5, "BE": 1, "QA": 0.5}),
    ("1. MVP Bretagne", "Sprint 4 : interface Streamlit, documentation, qualité", 9, 2, {"CP": 0.5, "PO": 0.3, "DS": 0.5, "FE": 1, "QA": 0.5}),
    ("Pilotage", "Pilotage Scrum, comités, reporting (phases 2 à 6)", 11, 34, {"CP": 0.5, "PO": 0.3}),
    ("2. Temps réel et IoT", "Intégration de l'API temps réel Météo-France", 11, 4, {"DE": 1, "BE": 0.5}),
    ("2. Temps réel et IoT", "Choix et achat des capteurs IoT (marché public)", 11, 6, {"IOT": 0.5}),
    ("2. Temps réel et IoT", "Pipeline de données et stockage (data lake)", 15, 8, {"DE": 1, "OPS": 0.5}),
    ("2. Temps réel et IoT", "Déploiement pilote de 50 capteurs chez des agriculteurs", 17, 6, {"IOT": 1, "DE": 0.5, "MET": 0.2}),
    ("3. Modèle v2 national", "Extension du modèle à toutes les régions", 19, 6, {"DS": 1, "DE": 0.5, "MET": 0.3}),
    ("3. Modèle v2 national", "Modèle multi-horizon J+1 à J+7 avec données IoT", 23, 8, {"DS": 1, "MET": 0.3}),
    ("3. Modèle v2 national", "MLOps : réentraînement automatique, suivi de dérive", 25, 6, {"OPS": 1, "DS": 0.3}),
    ("4. Application agriculteurs", "Ateliers UX avec agriculteurs, maquettes accessibles", 23, 4, {"FE": 1, "PO": 0.5}),
    ("4. Application agriculteurs", "Application web responsive et alertes SMS/push", 27, 8, {"FE": 1, "BE": 1, "QA": 0.5}),
    ("5. Recette et pilote", "Recette fonctionnelle et tests de charge", 35, 3, {"QA": 1, "BE": 0.5, "DS": 0.3}),
    ("5. Recette et pilote", "Audit RGAA et test d'intrusion (prestataires)", 36, 2, {"QA": 0.5, "OPS": 0.3}),
    ("5. Recette et pilote", "Bêta avec 30 agriculteurs pilotes", 37, 4, {"PO": 0.5, "DS": 0.3, "FE": 0.3, "MET": 0.3}),
    ("6. Mise en service", "Déploiement en production et formation", 41, 2, {"OPS": 1, "BE": 0.5, "PO": 0.5}),
    ("6. Mise en service", "Hypercare (support renforcé) et bilan", 43, 2, {"OPS": 0.3, "BE": 0.5, "DS": 0.3}),
]

# (semaine de fin, libellé)
JALONS = [
    (3, "J0 Lancement validé"),
    (11, "J1 Démo MVP / Go-NoGo"),
    (23, "J2 Données temps réel"),
    (35, "J3 Application prête"),
    (41, "J4 Go mise en service"),
    (45, "J5 Clôture"),
]

# (catégorie, poste, quantité, unité, prix unitaire € HT, source / hypothèse)
AUTRES_COUTS = [
    ("Matériel IoT", "Stations IoT (pluviomètre, T°, humidité, pression)", 50, "station", 700, "Devis indicatif station agro-météo connectée"),
    ("Matériel IoT", "Connectivité LoRaWAN / NB-IoT (1re année)", 50, "abonnement/an", 36, "Tarif opérateur IoT ~3 €/mois"),
    ("Matériel IoT", "Installation et maintenance des capteurs", 1, "forfait", 5000, "Déplacements en exploitation"),
    ("Hébergement", "Cloud dev / préproduction (hébergeur français bas carbone)", 11, "mois", 400, "OVHcloud / Scaleway, instances CPU"),
    ("Hébergement", "Cloud production (fin de projet)", 2, "mois", 900, "Haute disponibilité, région FR"),
    ("Outils", "GitHub Team", 110, "utilisateur.mois", 4, "10 utilisateurs x 11 mois"),
    ("Outils", "Jira Software Standard", 110, "utilisateur.mois", 8, "10 utilisateurs x 11 mois"),
    ("Données", "API Météo-France (open data)", 1, "forfait", 0, "Licence Etalab, gratuite"),
    ("Prestations", "Audit d'accessibilité RGAA", 1, "forfait", 8000, "Cabinet spécialisé"),
    ("Prestations", "Test d'intrusion (pentest)", 1, "forfait", 12000, "Prestataire qualifié PASSI"),
    ("Conduite du changement", "Formation, webinaires et supports agriculteurs", 1, "forfait", 6000, ""),
    ("Conduite du changement", "Indemnisation des agriculteurs pilotes", 30, "agriculteur", 200, "Temps passé en bêta"),
]

# Fonctionnement annuel après mise en service (poste, montant annuel € HT, hypothèse)
RUN = [
    ("Hébergement production", "=12*900", "900 €/mois"),
    ("Connectivité 50 capteurs", "=50*36", "36 €/capteur/an"),
    ("Maintenance capteurs", 5000, "forfait annuel"),
    ("Maintenance applicative (TMA)", "=0.15*Budget!E_RH_TOTAL", "15 % du coût de développement"),
]


def week_start(w: int) -> date:
    return DEBUT + timedelta(weeks=w)


def week_end(w: int, d: int) -> date:
    return week_start(w) + timedelta(weeks=d) - timedelta(days=3)  # vendredi


# --------------------------------------------------------------------- Gantt PNG
PHASE_COLORS = {
    "0. Cadrage": "#6B7280",
    "1. MVP Bretagne": "#2563EB",
    "Pilotage": "#A3A3A3",
    "2. Temps réel et IoT": "#0D9488",
    "3. Modèle v2 national": "#7C3AED",
    "4. Application agriculteurs": "#EA580C",
    "5. Recette et pilote": "#DB2777",
    "6. Mise en service": "#16A34A",
}


def gantt_png() -> None:
    fig, ax = plt.subplots(figsize=(15, 8.5))
    n = len(TACHES)
    for i, (phase, nom, w, d, _) in enumerate(TACHES):
        y = n - 1 - i
        ax.barh(y, d, left=w, color=PHASE_COLORS[phase], height=0.6)
        ax.text(w + d + 0.3, y, f"{d} sem.", va="center", fontsize=8, color="#374151")
    for w, label in JALONS:
        ax.axvline(w, color="#DC2626", lw=0.8, ls="--")
        ax.plot(w, n - 0.3, marker="D", color="#DC2626", markersize=6, clip_on=False)
        ax.text(w + 0.3, n - 0.1, label, rotation=35, fontsize=8, color="#DC2626", ha="left", va="bottom")
    ax.set_yticks(range(n))
    ax.set_yticklabels([t[1] for t in reversed(TACHES)], fontsize=8.5)
    noms_mois = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    mois = [date(2027, m, 1) for m in range(1, 13)]
    ax.set_xticks([(m - DEBUT).days / 7 for m in mois])
    ax.set_xticklabels([f"{noms_mois[m.month - 1]} {m.year}" for m in mois], fontsize=8)
    ax.set_xlim(0, 47)
    ax.set_ylim(-0.7, n + 2.2)
    ax.grid(axis="x", color="#E5E7EB")
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(
        handles=[Patch(color=c, label=p) for p, c in PHASE_COLORS.items()],
        loc="lower left", fontsize=8, ncol=2, frameon=False,
    )
    ax.set_title(
        f"Projet Goutte d'eau – Planning prévisionnel ({DEBUT:%d/%m/%Y} → {week_end(43, 2):%d/%m/%Y}, 45 semaines)",
        fontsize=12, loc="left", pad=48,
    )
    fig.tight_layout()
    fig.savefig(OUT / "gantt.png", dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------ Excel budget
FONT = "Arial"
BLUE = Font(name=FONT, color="0000FF")
GREEN = Font(name=FONT, color="008000")
BOLD = Font(name=FONT, bold=True)
HEAD = Font(name=FONT, bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor="1F3A5F")
SUB_FILL = PatternFill("solid", fgColor="DCE6F1")
YELLOW = PatternFill("solid", fgColor="FFFF00")
THIN = Border(bottom=Side(style="thin", color="BFBFBF"))
EUR = '#,##0 €;(#,##0 €);"-"'
NUM = '#,##0.0;(#,##0.0);"-"'


def style_header(ws, row: int, ncols: int, start: int = 1) -> None:
    for c in range(start, start + ncols):
        cell = ws.cell(row, c)
        cell.font, cell.fill = HEAD, HEAD_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def build_excel() -> dict:
    wb = Workbook()

    # ---- Hypothèses
    hy = wb.active
    hy.title = "Hypotheses"
    hy["A1"] = "Hypothèses du budget – Projet Goutte d'eau"
    hy["A1"].font = Font(name=FONT, bold=True, size=14)
    hy["A2"] = "Légende : texte bleu = hypothèse modifiable ; noir = formule ; vert = lien vers un autre onglet."
    hy["A2"].font = Font(name=FONT, italic=True, size=9)
    params = [
        ("Date de démarrage (lundi S1)", DEBUT, "dd/mm/yyyy", "Hypothèse : lancement après validation du cahier des charges"),
        ("Jours ouvrés par semaine", JOURS_SEMAINE, "0", ""),
        ("Provision pour aléas (contingence)", CONTINGENCE, "0%", "Pratique courante 10–15 % pour un projet IA"),
    ]
    for i, (lab, val, fmt, note) in enumerate(params, start=4):
        hy.cell(i, 1, lab).font = Font(name=FONT)
        c = hy.cell(i, 2, val)
        c.font, c.number_format, c.fill = BLUE, fmt, YELLOW
        hy.cell(i, 3, note).font = Font(name=FONT, italic=True, size=9)
    hy["A8"] = "Code"
    hy["B8"] = "Rôle"
    hy["C8"] = "TJM chargé (€ HT)"
    style_header(hy, 8, 3)
    for i, (code, role, tjm) in enumerate(ROLES, start=9):
        hy.cell(i, 1, code).font = BOLD
        hy.cell(i, 2, role).font = Font(name=FONT)
        c = hy.cell(i, 3, tjm)
        c.font, c.number_format = BLUE, EUR
    hy.cell(9 + len(ROLES), 1, "Source TJM : ordres de grandeur du marché français (coût interne chargé ou régie), à ajuster avec la DRH / les achats.").font = Font(name=FONT, italic=True, size=9)
    hy.column_dimensions["A"].width = 38
    hy.column_dimensions["B"].width = 38
    hy.column_dimensions["C"].width = 55
    tjm_row = {code: 9 + i for i, (code, _, _) in enumerate(ROLES)}

    # ---- Planning
    pl = wb.create_sheet("Planning")
    pl["A1"] = "Planning détaillé et charge par tâche"
    pl["A1"].font = Font(name=FONT, bold=True, size=14)
    pl["A2"] = "Les ETP (équivalents temps plein, en bleu) par rôle et par tâche sont modifiables ; charges, coûts et diagramme se recalculent."
    pl["A2"].font = Font(name=FONT, italic=True, size=9)
    first_role_col = 7  # G
    hdr = ["Phase", "Tâche", "Sem. début", "Durée (sem.)", "Date début", "Date fin", *CODES, "Charge (j.h)", "Coût (€ HT)"]
    HR = 5  # ligne d'en-tête
    for j, h in enumerate(hdr, start=1):
        pl.cell(HR, j, h)
    style_header(pl, HR, len(hdr))
    # ligne des TJM sous l'en-tête
    pl.cell(HR - 1, 6, "TJM →").font = BOLD
    for k, code in enumerate(CODES):
        c = pl.cell(HR - 1, first_role_col + k, f"=Hypotheses!$C${tjm_row[code]}")
        c.font, c.number_format = GREEN, '#,##0'
    last_role_col = first_role_col + len(CODES) - 1
    col_charge = last_role_col + 1
    col_cout = last_role_col + 2
    rl, rr = get_column_letter(first_role_col), get_column_letter(last_role_col)

    r0 = HR + 1
    for i, (phase, nom, w, d, alloc) in enumerate(TACHES):
        r = r0 + i
        pl.cell(r, 1, phase).font = Font(name=FONT)
        pl.cell(r, 2, nom).font = Font(name=FONT)
        c = pl.cell(r, 3, w + 1); c.font = BLUE
        c = pl.cell(r, 4, d); c.font = BLUE
        c = pl.cell(r, 5, f"=Hypotheses!$B$4+(C{r}-1)*7"); c.number_format = "dd/mm/yyyy"; c.font = Font(name=FONT)
        c = pl.cell(r, 6, f"=E{r}+D{r}*7-3"); c.number_format = "dd/mm/yyyy"; c.font = Font(name=FONT)
        for k, code in enumerate(CODES):
            v = alloc.get(code)
            c = pl.cell(r, first_role_col + k, v if v else None)
            c.font, c.number_format = BLUE, '0.0;;""'
        c = pl.cell(r, col_charge, f"=D{r}*Hypotheses!$B$5*SUM({rl}{r}:{rr}{r})")
        c.number_format, c.font = NUM, Font(name=FONT)
        c = pl.cell(r, col_cout, f"=D{r}*Hypotheses!$B$5*SUMPRODUCT({rl}{r}:{rr}{r},{rl}${HR-1}:{rr}${HR-1})")
        c.number_format, c.font = EUR, Font(name=FONT)
    rN = r0 + len(TACHES) - 1
    rt = rN + 1
    pl.cell(rt, 2, "TOTAL").font = BOLD
    for col in (col_charge, col_cout):
        L = get_column_letter(col)
        c = pl.cell(rt, col, f"=SUM({L}{r0}:{L}{rN})")
        c.font, c.number_format = BOLD, EUR if col == col_cout else NUM
    # Gantt en cellules (mise en forme conditionnelle)
    g0 = col_cout + 2
    for wk in range(47):
        c = pl.cell(HR, g0 + wk, wk + 1)
        c.font = Font(name=FONT, size=7, bold=True, color="FFFFFF")
        c.fill, c.alignment = HEAD_FILL, Alignment(horizontal="center")
        pl.column_dimensions[get_column_letter(g0 + wk)].width = 2.6
    pl.cell(HR - 1, g0, "Semaines (S1 = date de démarrage) →").font = BOLD
    gl, gr = get_column_letter(g0), get_column_letter(g0 + 46)
    first_g = f"{gl}{r0}"
    pl.conditional_formatting.add(
        f"{gl}{r0}:{gr}{rN}",
        FormulaRule(
            formula=[f"AND({gl}${HR}>=$C{r0},{gl}${HR}<$C{r0}+$D{r0})"],
            fill=PatternFill("solid", fgColor="2563EB"),
        ),
    )
    widths = {"A": 24, "B": 52, "C": 9, "D": 9, "E": 11, "F": 11}
    for k, v in widths.items():
        pl.column_dimensions[k].width = v
    for k in range(len(CODES)):
        pl.column_dimensions[get_column_letter(first_role_col + k)].width = 6
    pl.column_dimensions[get_column_letter(col_charge)].width = 11
    pl.column_dimensions[get_column_letter(col_cout)].width = 13
    pl.freeze_panes = pl.cell(HR + 1, 3)

    # ---- Budget
    bu = wb.create_sheet("Budget")
    bu["A1"] = "Budget prévisionnel – Projet Goutte d'eau (€ HT)"
    bu["A1"].font = Font(name=FONT, bold=True, size=14)

    # A. Ressources humaines par rôle
    bu["A3"] = "A. Ressources humaines par rôle"
    bu["A3"].font = BOLD
    for j, h in enumerate(["Code", "Rôle", "Jours-homme", "TJM (€)", "Coût (€ HT)"], start=1):
        bu.cell(4, j, h)
    style_header(bu, 4, 5)
    for k, (code, role, _) in enumerate(ROLES):
        r = 5 + k
        colL = get_column_letter(first_role_col + k)
        bu.cell(r, 1, code).font = BOLD
        bu.cell(r, 2, role).font = Font(name=FONT)
        c = bu.cell(r, 3, f"=SUMPRODUCT(Planning!$D${r0}:$D${rN},Planning!{colL}${r0}:{colL}${rN})*Hypotheses!$B$5")
        c.number_format, c.font = NUM, GREEN
        c = bu.cell(r, 4, f"=Hypotheses!$C${tjm_row[code]}")
        c.number_format, c.font = EUR, GREEN
        c = bu.cell(r, 5, f"=C{r}*D{r}")
        c.number_format, c.font = EUR, Font(name=FONT)
    rA = 5 + len(ROLES)
    bu.cell(rA, 2, "Sous-total ressources humaines").font = BOLD
    c = bu.cell(rA, 3, f"=SUM(C5:C{rA-1})"); c.font, c.number_format = BOLD, NUM
    c = bu.cell(rA, 5, f"=SUM(E5:E{rA-1})"); c.font, c.number_format = BOLD, EUR
    E_RH = f"$E${rA}"

    # B. Autres coûts
    rB = rA + 2
    bu.cell(rB, 1, "B. Matériel, hébergement, outils et prestations").font = BOLD
    for j, h in enumerate(["Catégorie", "Poste", "Quantité", "Prix unitaire (€)", "Coût (€ HT)", "Unité", "Source / hypothèse"], start=1):
        bu.cell(rB + 1, j, h)
    style_header(bu, rB + 1, 7)
    for k, (cat, poste, q, unite, pu, src) in enumerate(AUTRES_COUTS):
        r = rB + 2 + k
        bu.cell(r, 1, cat).font = Font(name=FONT)
        bu.cell(r, 2, poste).font = Font(name=FONT)
        c = bu.cell(r, 3, q); c.font = BLUE
        c = bu.cell(r, 4, pu); c.font, c.number_format = BLUE, EUR
        c = bu.cell(r, 5, f"=C{r}*D{r}"); c.number_format, c.font = EUR, Font(name=FONT)
        bu.cell(r, 6, unite).font = Font(name=FONT, size=9)
        bu.cell(r, 7, src).font = Font(name=FONT, italic=True, size=9)
    rBe = rB + 1 + len(AUTRES_COUTS)
    rBt = rBe + 1
    bu.cell(rBt, 2, "Sous-total hors ressources humaines").font = BOLD
    c = bu.cell(rBt, 5, f"=SUM(E{rB+2}:E{rBe})"); c.font, c.number_format = BOLD, EUR

    # C. Synthèse
    rC = rBt + 2
    bu.cell(rC, 1, "C. Synthèse").font = BOLD
    synth = [
        ("Ressources humaines", f"={E_RH}"),
        ("Matériel, hébergement, outils, prestations", f"=E{rBt}"),
        ("Total avant aléas", f"=E{rC+1}+E{rC+2}"),
        ("Provision pour aléas", f"=E{rC+3}*Hypotheses!$B$6"),
        ("BUDGET TOTAL DU PROJET (€ HT)", f"=E{rC+3}+E{rC+4}"),
        ("BUDGET TOTAL DU PROJET (€ TTC, TVA 20 %)", f"=E{rC+5}*1.2"),
    ]
    for k, (lab, f) in enumerate(synth, start=1):
        r = rC + k
        bu.cell(r, 2, lab).font = BOLD if "TOTAL" in lab else Font(name=FONT)
        c = bu.cell(r, 5, f)
        c.number_format = EUR
        c.font = BOLD if "TOTAL" in lab else Font(name=FONT)
        if "TOTAL" in lab:
            for col in range(1, 6):
                bu.cell(r, col).fill = SUB_FILL
    rCt = rC + 5

    # D. Répartition par phase
    rD = rC + len(synth) + 2
    bu.cell(rD, 1, "D. Coût RH par phase").font = BOLD
    for j, h in enumerate(["", "Phase", "Charge (j.h)", "", "Coût RH (€ HT)", "Part"], start=1):
        bu.cell(rD + 1, j, h)
    style_header(bu, rD + 1, 6)
    phases = list(dict.fromkeys(t[0] for t in TACHES))
    cL, kL = get_column_letter(col_charge), get_column_letter(col_cout)
    for k, ph in enumerate(phases):
        r = rD + 2 + k
        bu.cell(r, 2, ph).font = Font(name=FONT)
        c = bu.cell(r, 3, f'=SUMIF(Planning!$A${r0}:$A${rN},B{r},Planning!${cL}${r0}:${cL}${rN})'); c.number_format, c.font = NUM, GREEN
        c = bu.cell(r, 5, f'=SUMIF(Planning!$A${r0}:$A${rN},B{r},Planning!${kL}${r0}:${kL}${rN})'); c.number_format, c.font = EUR, GREEN
        c = bu.cell(r, 6, f"=IF({E_RH}=0,0,E{r}/{E_RH})"); c.number_format = "0.0%"
    rDe = rD + 1 + len(phases)
    bu.cell(rDe + 1, 2, "Contrôle (doit être égal au sous-total RH)").font = Font(name=FONT, italic=True)
    c = bu.cell(rDe + 1, 5, f"=SUM(E{rD+2}:E{rDe})-{E_RH}"); c.number_format = EUR

    # E. Fonctionnement annuel
    rE = rDe + 3
    bu.cell(rE, 1, "E. Coût de fonctionnement annuel après mise en service (hors projet)").font = BOLD
    for j, h in enumerate(["", "Poste", "Hypothèse", "", "Coût annuel (€ HT)"], start=1):
        bu.cell(rE + 1, j, h)
    style_header(bu, rE + 1, 5)
    for k, (poste, val, hyp) in enumerate(RUN):
        r = rE + 2 + k
        bu.cell(r, 2, poste).font = Font(name=FONT)
        bu.cell(r, 3, hyp).font = Font(name=FONT, italic=True, size=9)
        if isinstance(val, str):
            val = val.replace("Budget!E_RH_TOTAL", E_RH)
            c = bu.cell(r, 5, val); c.font = Font(name=FONT)
        else:
            c = bu.cell(r, 5, val); c.font = BLUE
        c.number_format = EUR
    rEe = rE + 1 + len(RUN)
    bu.cell(rEe + 1, 2, "Total fonctionnement annuel").font = BOLD
    c = bu.cell(rEe + 1, 5, f"=SUM(E{rE+2}:E{rEe})"); c.font, c.number_format = BOLD, EUR

    for k, v in {"A": 22, "B": 52, "C": 14, "D": 16, "E": 18, "F": 18, "G": 40}.items():
        bu.column_dimensions[k].width = v
    bu["E" + str(rCt)].comment = Comment("Montant à soumettre à la direction financière.", "Goutte d'eau")

    wb.move_sheet("Budget", offset=-2)
    wb.active = 0
    wb.calculation.fullCalcOnLoad = True  # Excel recalcule tout à l'ouverture
    path = OUT / "budget_previsionnel.xlsx"
    wb.save(path)
    return {"path": path, "rows": {"rA": rA, "rBt": rBt, "rCt": rCt, "rDe": rDe, "rEe": rEe}}


def python_totals() -> dict:
    """Mêmes calculs en Python, pour contrôler les formules Excel."""
    tjm = {c: t for c, _, t in ROLES}
    jh = {c: 0.0 for c in CODES}
    by_phase: dict[str, float] = {}
    for phase, _, _, d, alloc in TACHES:
        for code, fte in alloc.items():
            jh[code] += d * JOURS_SEMAINE * fte
            by_phase[phase] = by_phase.get(phase, 0) + d * JOURS_SEMAINE * fte * tjm[code]
    rh = sum(jh[c] * tjm[c] for c in CODES)
    autres = sum(q * pu for *_, q, _, pu, _ in [(a, b, q, u, p, s) for a, b, q, u, p, s in AUTRES_COUTS])
    avant = rh + autres
    total = avant * (1 + CONTINGENCE)
    run = 12 * 900 + 50 * 36 + 5000 + 0.15 * rh
    return {"jh": jh, "jh_total": sum(jh.values()), "rh": rh, "autres": autres, "avant": avant,
            "alea": avant * CONTINGENCE, "total": total, "ttc": total * 1.2, "by_phase": by_phase, "run": run}


if __name__ == "__main__":
    gantt_png()
    info = build_excel()
    t = python_totals()
    print(f"Excel : {info['path']}")
    print(f"Fin du projet : {week_end(43, 2):%d/%m/%Y}")
    print(f"Jours-homme : {t['jh_total']:.1f}  ->  " + ", ".join(f"{k}={v:.1f}" for k, v in t["jh"].items()))
    print(f"RH : {t['rh']:,.0f} €   Autres : {t['autres']:,.0f} €   Avant aléas : {t['avant']:,.0f} €")
    print(f"Aléas : {t['alea']:,.0f} €   TOTAL HT : {t['total']:,.0f} €   TTC : {t['ttc']:,.0f} €")
    print("Par phase : " + ", ".join(f"{k}={v:,.0f}" for k, v in t["by_phase"].items()))
    print(f"Run annuel : {t['run']:,.0f} €")
