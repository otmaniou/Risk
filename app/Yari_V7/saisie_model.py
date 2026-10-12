"""Ya-Risk — feuilles Saisie et Etatsfin du modèle ANALYSTE V20 (côté serveur).

Le modèle préparé (formules exactes, styles, cellules de saisie) est dans bilan_grid/model_saisie.js, généré par
tools/build_saisie_model.py. Le navigateur l'évalue en direct (wb_engine.js) ; ce module produit, à la validation,
la liste des écritures à reporter dans l'Excel généré par le worker (validation/saisie_excel.json), pour que
l'Excel et l'écran affichent exactement la même chose.

Saisies analyste, fichier <dossier>/saisie.json :
    {"annees": {"2024": {"48": 12.5, ...}}, "etatsfin": {"2024": {"97": 100.0}}, "textes": {"C3": "Groupe X"},
     "historique": [...]}
Les montants sont en KDZD (unité de la feuille Saisie). Ils sont rangés par exercice, pas par colonne : ils
restent à leur place si un exercice est ajouté au dossier.
"""
import calendar
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

MODEL_JS = Path(__file__).resolve().parent / "bilan_grid" / "model_saisie.js"
PREFIX = "window.YR_MODEL="


@lru_cache(maxsize=1)
def load_model():
    txt = MODEL_JS.read_text(encoding="utf-8").strip()
    if not txt.startswith(PREFIX):
        raise ValueError("model_saisie.js invalide")
    return json.loads(txt[len(PREFIX):].rstrip(";"))


def empty_inputs():
    return {"annees": {}, "etatsfin": {}, "crf": {}, "textes": {}, "historique": []}


def latest_year(years):
    ys = [int(y) for y in years or []]
    return max(ys) if ys else None


def saisie_col(latest, year):
    k = latest - int(year)
    cols = load_model()["saisieYearCols"]
    return cols[k] if 0 <= k < len(cols) else None


def etats_col(latest, year):
    k = latest - int(year)
    cols = load_model()["etatsYearCols"]
    return cols[k][1] if 0 <= k < len(cols) else None


def year_of_input(latest, sheet, addr):
    """Exercice d'une cellule de saisie analyste (None si la cellule n'est pas une saisie autorisée)."""
    m = load_model(); col = "".join(ch for ch in addr if ch.isalpha())
    if sheet == "Saisie" and addr in saisie_input_cells():
        cols = m["saisieYearCols"]
        return latest - cols.index(col) if col in cols else None
    if sheet == "Etatsfin" and addr in set(m["etatsInputs"]):
        cols = [c[1] for c in m["etatsYearCols"]]
        return latest - cols.index(col) if col in cols else None
    crf = m.get("crf") or {}
    if f"{sheet}!{addr}" in set(crf.get("inputs") or []):
        cols = crf["yearCols"].get(sheet) or []
        return latest - cols.index(col) if col in cols else None
    return None


def is_text_input(sheet, addr):
    if sheet == "Saisie" and addr == "C3":
        return True
    crf = load_model().get("crf") or {}
    return f"{sheet}!{addr}" in set(crf.get("text") or [])


def saisie_input_cells():
    return set(load_model()["saisieInputs"])


def dyn_liasse(cons):
    """Valeurs des feuilles Saisie actif / passif / TCR (KDZD), comme les écrit build_client_excel."""
    m = load_model(); cfg = m["cfg"]; ranks = m["ranks"]; out = {}
    latest = latest_year(cons.get("years"))
    if latest is None:
        return out
    allowed = {sh: set(v) for sh, v in m["liasseInputs"].items()}
    colmap = {"ACTIF": ("Saisie actif", cfg["ACTIF_ROWS"], lambda rk, c: cfg["ACTIF_GROUPES"][rk][["brut", "amort", "net"].index(c)]),
              "PASSIF": ("Saisie passif", cfg["PASSIF_ROWS"], lambda rk, c: cfg["PASSIF_COLS"][rk]),
              "TCR": ("Saisie TCR", cfg["TCR_ROWS"], lambda rk, c: cfg["TCR_PAIRES"][rk][["debit", "credit"].index(c)])}
    for table, (sheet, rows, colf) in colmap.items():
        for rid, vals in (cons.get("data", {}).get(table) or {}).items():
            if rid not in rows:
                continue
            for ck, v in vals.items():
                y, c = ck.split(":")
                k = latest - int(y)
                if v is None or not 0 <= k < len(ranks):
                    continue
                addr = f"{colf(ranks[k], c)}{rows[rid]}"
                if addr in allowed[sheet]:
                    out[f"{sheet}!{addr}"] = float(v) / 1000.0
    return out


def dyn_saisie(years, inputs, client_name):
    """En-têtes (dates d'exercice, société), saisies analyste de Saisie et Etatsfin."""
    m = load_model(); out = {}
    latest = latest_year(years)
    out["Saisie!C2"] = client_name or ""
    out["Saisie!C3"] = ((inputs or {}).get("textes") or {}).get("C3") or None
    if latest is None:
        return out
    for k, col in enumerate(m["saisieYearCols"]):
        out[f"Saisie!{col}3"] = {"d": f"{latest - k}-12-31"}
    allowed = saisie_input_cells()
    for y, rows in ((inputs or {}).get("annees") or {}).items():
        col = saisie_col(latest, y)
        if not col:
            continue
        for r, v in rows.items():
            a = f"{col}{int(r)}"
            if a in allowed and v is not None:
                out[f"Saisie!{a}"] = float(v)
    eallowed = set(m["etatsInputs"])
    for y, rows in ((inputs or {}).get("etatsfin") or {}).items():
        col = etats_col(latest, y)
        if not col:
            continue
        for r, v in rows.items():
            a = f"{col}{int(r)}"
            if a in eallowed and v is not None:
                out[f"Etatsfin!{a}"] = float(v)
    return out


def dyn_crf(years, inputs, today=None):
    """Feuilles CRF : en-têtes d'exercice, date de création, réponses texte et saisies / surcharges analyste."""
    crf = load_model().get("crf") or {}; out = {}
    latest = latest_year(years)
    if not crf or latest is None:
        return out
    today = today or date.today()
    for sh, a in crf["created"]:
        out[f"{sh}!{a}"] = today.strftime("%d/%m/%Y")
    for sh, a, k, r in crf["headers"]:
        y = latest - k
        out[f"{sh}!{a}"] = f"31/12/{y}" if r == 5 else f"01/01/{y}" if r == 6 else (366 if calendar.isleap(y) else 365)
    for key, v in ((inputs or {}).get("textes") or {}).items():
        if "!" in key and key in set(crf["text"]) and v not in (None, ""):
            out[key] = v
    allowed = set(crf["inputs"])
    for y, cells in ((inputs or {}).get("crf") or {}).items():
        for key, v in cells.items():
            sh, row = key.rsplit("!", 1)
            cols = crf["yearCols"].get(sh) or []
            k = latest - int(y)
            if v is None or not 0 <= k < len(cols):
                continue
            a = f"{sh}!{cols[k]}{int(row)}"
            if a in allowed:
                out[a] = float(v)
    return out


def excel_writes(years, inputs, client_name):
    """Écritures à appliquer à l'Excel généré : préparation du modèle (formules par exercice, valeurs d'exemple
    vidées, réparations) puis en-têtes et saisies analyste. Format : [feuille, cellule, valeur | "=formule" | {"d": iso} | None]."""
    m = load_model()
    writes = [list(x) for x in m["patch"]]
    dyn = dyn_saisie(years, inputs, client_name)
    dyn.update(dyn_crf(years, inputs))
    for k, v in dyn.items():
        sh, a = k.rsplit("!", 1)
        writes.append([sh, a, v])
    return writes
