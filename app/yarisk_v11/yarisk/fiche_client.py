"""Fiche client YaRisk : données de démonstration (crédits, garanties, utilisations, Centrale des risques),
synthèse des états financiers, questions Risques → commercial, proposition de crédit et RWA (approche standard CRR).

Toutes les données bancaires de ce module sont SIMULÉES pour la démonstration : elles sont générées de façon
déterministe à partir du NIF et calibrées sur les états financiers extraits par YaRisk quand ils existent.
"""
import hashlib
import math
import random
from datetime import date, timedelta

import bilan_view as bv

# ---------------------------------------------------------------------------
# Référentiel des lignes de crédit
# ---------------------------------------------------------------------------
# nature : bilan (décaissement) ou signature (engagement hors bilan)
# ccf_sig : facteur de conversion de l'engagement émis (CRR3, art. 111) ; revocable : ligne annulable à tout moment
TYPES = {
    "FC":  {"lib": "Facilité de caisse", "cat": "CT", "nature": "bilan", "revocable": True},
    "AMC": {"lib": "Avances sur marchandises", "cat": "CT", "nature": "bilan", "revocable": False},
    "ESC": {"lib": "Escompte commercial", "cat": "CT", "nature": "bilan", "revocable": False},
    "LC":  {"lib": "Lettres de crédit import", "cat": "SIG", "nature": "signature", "ccf_sig": 0.20, "revocable": False},
    "CAU": {"lib": "Cautions de marché", "cat": "SIG", "nature": "signature", "ccf_sig": 0.50, "revocable": False},
    "CMT": {"lib": "Crédit moyen terme", "cat": "MT", "nature": "bilan", "revocable": False, "amortissable": True},
    "LEA": {"lib": "Leasing (crédit-bail)", "cat": "LEA", "nature": "bilan", "revocable": False, "amortissable": True},
}
CAT_LABELS = {"CT": "Crédits d'exploitation (CT)", "MT": "Moyen terme", "LEA": "Leasing", "SIG": "Engagements par signature"}

GARANTIE_TYPES = {
    "HYP": "Hypothèque immobilière",
    "NFC": "Nantissement du fonds de commerce",
    "NMAT": "Nantissement de matériel",
    "CPS": "Caution personnelle et solidaire des associés",
    "DAT": "Dépôt à terme nanti",
    "GBQ": "Garantie bancaire (contre-garantie)",
    "DOM": "Domiciliation des recettes / marchés",
}
# Éligibilité à l'atténuation du risque de crédit en approche standard (CRR) — simplifié
CRM = {"DAT": "cash", "GBQ": "garantie", "HYP": "immobilier"}

FIN_KEYS = [
    ("ca", "Chiffre d'affaires"), ("ebe", "Excédent brut d'exploitation"), ("rn", "Résultat net"),
    ("fp", "Capitaux propres"), ("tb", "Total bilan"), ("dfin", "Dettes financières"),
    ("bfr", "BFR d'exploitation"), ("fr", "Fonds de roulement"), ("treso", "Trésorerie nette"),
]


def _rng(*parts):
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def _r(x, step=1000):
    return float(round(x / step) * step)


# ---------------------------------------------------------------------------
# États financiers : agrégats par exercice à partir de la consolidation YaRisk
# ---------------------------------------------------------------------------
def financials(cons):
    """{annee: {cle: valeur DZD}} + ratios, à partir des données consolidées (après corrections)."""
    out = {}
    for y in cons.get("years") or []:
        ra, rp, rt = (bv._year_rows(cons, t, y) for t in ("ACTIF", "PASSIF", "TCR"))
        A = bv.compute_balance("ACTIF", ra, {})
        P = bv.compute_balance("PASSIF", rp, {})
        T = bv.compute_tcr(rt, {})

        def a(r):
            c = A.get((r, "net_n")); return c.value if c and c.value is not None else None

        def p(r):
            c = P.get((r, "n")); return c.value if c and c.value is not None else None

        def t(r):
            c = T.get((r, "n")); return c.value if c and c.value is not None else None
        z = lambda v: v or 0.0
        d = {
            "ca": t("chiffre_affaires_net"), "production": t("production_exercice"),
            "conso": -z(t("consommations_exercice")) if t("consommations_exercice") is not None else None,
            "va": t("valeur_ajoutee_exploitation"), "ebe": t("excedent_brut_exploitation"),
            "ro": t("resultat_operationnel"), "rn": t("resultat_net_exercice"),
            "dot": -z(t("dotations_amortissements")), "ffin": -z(t("charges_financieres")),
            "fp": p("total_capitaux_propres"), "capital": p("capital_emis"), "tb": a("total_general_actif") or p("total_general_passif"),
            "anc": a("total_actif_non_courant"), "stocks": a("stocks_encours"), "clients": a("clients"),
            "fournisseurs": p("fournisseurs_rattaches"), "tres_actif": a("tresorerie_actif"), "tres_passif": p("tresorerie_passif"),
            "emprunts": p("emprunts_dettes_financieres"), "pnc": p("total_passifs_non_courants"),
        }
        if all(v is None for v in d.values()):
            continue
        d["dfin"] = z(d["emprunts"]) + z(d["tres_passif"])
        d["bfr"] = z(d["stocks"]) + z(d["clients"]) - z(d["fournisseurs"])
        d["fr"] = z(d["fp"]) + z(d["pnc"]) - z(d["anc"])
        d["treso"] = z(d["tres_actif"]) - z(d["tres_passif"])
        d["caf"] = z(d["rn"]) + z(d["dot"])
        ca = d["ca"] or 0
        d["r_marge_ebe"] = d["ebe"] / ca if ca and d["ebe"] is not None else None
        d["r_autonomie"] = d["fp"] / d["tb"] if d["tb"] and d["fp"] is not None else None
        d["r_dfin_ebe"] = d["dfin"] / d["ebe"] if d["ebe"] and d["ebe"] > 0 else None
        d["r_gearing"] = d["dfin"] / d["fp"] if d["fp"] and d["fp"] > 0 else None
        d["r_couv_ff"] = d["ebe"] / d["ffin"] if d["ffin"] and d["ebe"] is not None else None
        d["j_clients"] = d["clients"] / ca * 360 if ca and d["clients"] is not None else None
        d["j_stocks"] = d["stocks"] / ca * 360 if ca and d["stocks"] is not None else None
        d["j_fourn"] = d["fournisseurs"] / d["conso"] * 360 if d.get("conso") and d["fournisseurs"] is not None else None
        out[y] = d
    return out


RATIOS = [
    ("r_marge_ebe", "Marge d'EBE (EBE / CA)", "pct"), ("r_autonomie", "Autonomie financière (FP / total bilan)", "pct"),
    ("r_dfin_ebe", "Dettes financières / EBE", "x"), ("r_gearing", "Gearing (dettes financières / FP)", "x"),
    ("r_couv_ff", "Couverture des frais financiers (EBE / FF)", "x"), ("j_clients", "Délai clients (jours de CA)", "j"),
    ("j_stocks", "Stocks (jours de CA)", "j"), ("j_fourn", "Délai fournisseurs (jours d'achats)", "j"),
]


# ---------------------------------------------------------------------------
# Données bancaires simulées
# ---------------------------------------------------------------------------
def _daily(rng, kind, limit, days, start):
    """Série quotidienne d'utilisation (DZD) selon le type de ligne."""
    vals = []
    if kind == "FC":
        x = 0.70 * limit
        for i in range(days):
            d = start + timedelta(days=i)
            target = 0.72 * limit + (0.18 * limit if d.day >= 24 else 0)     # pics de fin de mois (salaires, fournisseurs)
            x = x + 0.35 * (target - x) + rng.gauss(0, 0.06 * limit)
            if i > days - 120 and rng.random() < 0.06:
                x = limit * (1.02 + rng.random() * 0.08)                     # dépassements récents
            vals.append(max(0.0, min(x, 1.12 * limit)))
    elif kind == "AMC":
        x = 0.5 * limit
        for i in range(days):
            season = 0.55 + 0.30 * math.sin(2 * math.pi * (i + 40) / 365)
            x = x + 0.2 * (season * limit - x) + rng.gauss(0, 0.03 * limit)
            vals.append(max(0.0, min(x, limit)))
    elif kind == "ESC":
        x = 0.7 * limit
        for i in range(days):
            if i % 7 == 0:
                x += rng.uniform(0.08, 0.20) * limit                          # remises hebdomadaires
            x -= rng.uniform(0.017, 0.023) * limit + 0.02 * (x - 0.75 * limit)  # échéances
            x = max(0.30 * limit, min(x, 0.98 * limit))
            vals.append(x)
    elif kind == "LC":
        opened = []
        for i in range(days):
            if rng.random() < 0.035:
                opened.append([rng.uniform(0.10, 0.28) * limit, rng.randint(60, 120)])
            for o in opened:
                o[1] -= 1
            opened = [o for o in opened if o[1] > 0]
            tot = sum(o[0] for o in opened)
            while tot > limit and opened:
                opened.pop(0); tot = sum(o[0] for o in opened)
            vals.append(tot)
    elif kind == "CAU":
        x = 0.6 * limit
        for i in range(days):
            if rng.random() < 0.02:
                x += rng.uniform(-0.12, 0.15) * limit
            x = max(0.3 * limit, min(x, 0.95 * limit))
            vals.append(x)
    return vals


def _amortissable(limit, months_total, months_elapsed_at_start, days, start, freq_months):
    """Capital restant dû quotidien d'un prêt amortissable (échéances constantes en capital)."""
    vals, per = [], limit / (months_total / freq_months)
    for i in range(days):
        d = start + timedelta(days=i)
        m = months_elapsed_at_start + (d.year - start.year) * 12 + d.month - start.month
        paid = max(0, int(m // freq_months))
        vals.append(max(0.0, limit - per * paid))
    return vals


def simulate(nif, raison, fin, arrete=None):
    """Jeu de données de démonstration complet pour un client."""
    rng = _rng("yarisk-demo", nif or raison or "client")
    arrete = arrete or (date.today() - timedelta(days=1))
    days = 365
    start = arrete - timedelta(days=days - 1)
    last = fin[max(fin)] if fin else {}
    ca = last.get("ca") or 1.2e9
    achats = last.get("conso") or 0.65 * ca
    stocks = last.get("stocks") or 0.12 * ca
    clients = last.get("clients") or 0.2 * ca
    lim = {
        "FC": _r(ca * 15 / 360, 1e6), "AMC": _r(stocks * 0.45, 1e6), "ESC": _r(clients * 0.55, 1e6),
        "LC": _r(achats * 0.35 * 3 / 12, 1e6), "CAU": _r(ca * 0.05, 1e6),
        "CMT": _r(max(0.05 * ca, 60e6), 1e6), "LEA": _r(max(0.025 * ca, 25e6), 1e6),
    }
    fac = []
    for k, t in TYPES.items():
        if t.get("amortissable"):
            if k == "CMT":
                series = _amortissable(lim[k], 60, 14, days, start, 3)
                info = {"duree_mois": 60, "periodicite": "trimestrielle", "taux": 6.25, "date_mise_en_place": (start - timedelta(days=14 * 30)).isoformat(),
                        "echeance": (start + timedelta(days=46 * 30)).isoformat()}
            else:
                series = _amortissable(lim[k], 48, 7, days, start, 1)
                info = {"duree_mois": 48, "periodicite": "mensuelle", "taux": 7.0, "date_mise_en_place": (start - timedelta(days=7 * 30)).isoformat(),
                        "echeance": (start + timedelta(days=41 * 30)).isoformat(), "bien": "Ligne de conditionnement et chariots élévateurs"}
        else:
            series = _daily(rng, k, lim[k], days, start)
            info = {"taux": {"FC": 6.75, "AMC": 6.5, "ESC": 6.0, "LC": 1.0, "CAU": 1.5}[k],
                    "echeance": (arrete + timedelta(days=rng.randint(40, 300))).isoformat()}
            if t["nature"] == "signature":
                info["taux_lib"] = "commission % / an"
        fac.append({"id": k, "type": k, "libelle": t["lib"], "categorie": t["cat"], "nature": t["nature"],
                    "autorisation": lim[k], "utilisation": _r(series[-1]), "serie": [_r(v) for v in series], **info})
    # Impayés (événements)
    imp = [
        {"date": (arrete - timedelta(days=74)).isoformat(), "ligne": "ESC", "objet": "Effet escompté retourné impayé (client du client)",
         "montant": _r(lim["ESC"] * 0.04), "jours_retard": 18, "statut": "Régularisé"},
        {"date": (arrete - timedelta(days=21)).isoformat(), "ligne": "CMT", "objet": "Échéance trimestrielle du crédit moyen terme",
         "montant": _r(lim["CMT"] / 20), "jours_retard": 21, "statut": "En cours"},
    ]
    # Garanties
    g = [
        {"id": "G1", "type": "HYP", "libelle": GARANTIE_TYPES["HYP"], "detail": "Local commercial et entrepôt, zone industrielle (1er rang)",
         "montant": _r(lim["CMT"] * 1.3, 1e6), "valeur": _r(lim["CMT"] * 1.6, 1e6), "date_expertise": (arrete - timedelta(days=4 * 365 + 30)).isoformat(),
         "echeance": None, "lignes": ["CMT"]},
        {"id": "G2", "type": "NMAT", "libelle": GARANTIE_TYPES["NMAT"], "detail": "Matériel de production financé",
         "montant": _r(lim["CMT"] * 0.4, 1e6), "valeur": _r(lim["CMT"] * 0.35, 1e6), "date_expertise": (arrete - timedelta(days=500)).isoformat(),
         "echeance": None, "lignes": ["CMT"]},
        {"id": "G3", "type": "CPS", "libelle": GARANTIE_TYPES["CPS"], "detail": "Associés gérants (2 personnes)",
         "montant": _r(lim["FC"] + lim["AMC"] + lim["ESC"], 1e6), "valeur": None, "date_expertise": None, "echeance": None, "lignes": ["FC", "AMC", "ESC"]},
        {"id": "G4", "type": "DAT", "libelle": GARANTIE_TYPES["DAT"], "detail": "Dépôt à terme 12 mois, même devise",
         "montant": _r(lim["LC"] * 0.25, 1e6), "valeur": _r(lim["LC"] * 0.25, 1e6), "date_expertise": None,
         "echeance": (arrete + timedelta(days=150)).isoformat(), "lignes": ["LC"]},
        {"id": "G5", "type": "GBQ", "libelle": GARANTIE_TYPES["GBQ"], "detail": "Contre-garantie d'une banque de la place",
         "montant": _r(lim["CAU"] * 0.5, 1e6), "valeur": _r(lim["CAU"] * 0.5, 1e6), "date_expertise": None,
         "echeance": (arrete + timedelta(days=210)).isoformat(), "lignes": ["CAU"]},
        {"id": "G6", "type": "DOM", "libelle": GARANTIE_TYPES["DOM"], "detail": "Domiciliation de 40 % du chiffre d'affaires",
         "montant": None, "valeur": None, "date_expertise": None, "echeance": None, "lignes": ["FC", "ESC"]},
    ]
    # Centrale des risques Banque d'Algérie (mensuelle, 24 mois)
    months = []
    m0 = date(arrete.year, arrete.month, 1)
    for i in range(23, -1, -1):
        y, m = m0.year, m0.month - i
        while m <= 0:
            m += 12; y -= 1
        months.append(date(y, m, 1))
    cr = []
    base_other = {"CT": 0.9 * (lim["FC"] + lim["AMC"] + lim["ESC"]), "MT": 0.35 * lim["CMT"], "LEA": 0.0, "SIG": 0.6 * (lim["LC"] + lim["CAU"])}
    for j, mth in enumerate(months):
        # Fin de mois : la série quotidienne couvre 12 mois ; avant, on extrapole.
        endm = (date(mth.year + (mth.month // 12), mth.month % 12 + 1, 1) - timedelta(days=1))
        idx = (endm - start).days
        bnp = {"CT": 0.0, "MT": 0.0, "LEA": 0.0, "SIG": 0.0}
        for f in fac:
            if 0 <= idx < days:
                v = f["serie"][idx]
            elif idx >= days:
                v = f["serie"][-1]
            else:
                v = f["serie"][0] * (1 + 0.01 * (-idx / 30)) if f["type"] in ("CMT", "LEA") else sum(f["serie"][:30]) / 30 * rng.uniform(0.85, 1.0)
                if f["type"] == "LEA" and idx < -210:
                    v = 0.0
            bnp[f["categorie"]] += v
        other = {}
        growth = 1 + 0.025 * max(0, j - 12)                                   # hausse ailleurs sur 12 mois
        other["CT"] = base_other["CT"] * growth * rng.uniform(0.95, 1.05)
        other["MT"] = base_other["MT"] + (0.9 * lim["CMT"] if j >= 16 else 0)  # nouveau MT ailleurs il y a 8 mois
        other["LEA"] = 0.0
        other["SIG"] = base_other["SIG"] * rng.uniform(0.9, 1.1)
        cr.append({"mois": mth.isoformat()[:7], "bnp": {k: _r(v) for k, v in bnp.items()}, "autres": {k: _r(v) for k, v in other.items()},
                   "nb_banques": 3 if j >= 16 else 2})
    info = {
        "raison_sociale": raison, "nif": nif, "rc": "16/00-" + str(rng.randint(1000000, 9999999)) + " B " + str(rng.randint(5, 18)).zfill(2),
        "forme_juridique": "SARL", "date_creation": str(2004 + rng.randint(0, 10)), "effectif": 80 + rng.randint(0, 220),
        "dirigeant": "Gérant (identité fictive de démonstration)", "actionnariat": "2 associés personnes physiques (60 % / 40 %)",
        "relation_depuis": str(2012 + rng.randint(0, 6)), "agence": "Centre d'affaires Entreprises — Alger",
        "charge_affaires": "Chargé d'affaires Corporate (démo)", "note_crf": str(5 + rng.randint(0, 2)),
        "derniere_revue": (arrete - timedelta(days=380)).isoformat(),
    }
    return {"simule": True, "arrete": arrete.isoformat(), "debut_serie": start.isoformat(), "client": info,
            "facilites": fac, "impayes": imp, "garanties": g, "centrale_risques": cr}


# ---------------------------------------------------------------------------
# Indicateurs d'utilisation
# ---------------------------------------------------------------------------
def usage_stats(f):
    s, L = f["serie"], f["autorisation"] or 0
    if not s or not L:
        return {}
    over = [v > L * 1.0001 for v in s]
    run = best = 0
    for o in over:
        run = run + 1 if o else 0
        best = max(best, run)
    last90 = s[-90:]
    return {"taux_moyen": sum(s) / len(s) / L, "taux_90j": sum(last90) / len(last90) / L, "max": max(s), "taux_max": max(s) / L,
            "jours_depassement": sum(over), "jours_depassement_90j": sum(over[-90:]), "max_consecutifs": best,
            "depassement_max": max(0.0, max(s) - L)}


def signals(data, fin):
    """Signaux d'alerte pour l'analyste (liste de (niveau, texte))."""
    out = []
    for f in data["facilites"]:
        st_ = usage_stats(f)
        if not st_:
            continue
        if st_["jours_depassement_90j"]:
            out.append(("HIGH" if st_["max_consecutifs"] >= 5 else "MEDIUM",
                        f"{f['libelle']} : {st_['jours_depassement_90j']} jour(s) de dépassement sur 90 jours "
                        f"(max {st_['max_consecutifs']} jours consécutifs, pointe {fmt(st_['depassement_max'])} DZD au-delà de l'autorisation)."))
        if f["type"] == "FC" and st_["taux_90j"] > 0.85:
            out.append(("MEDIUM", f"Facilité de caisse utilisée à {st_['taux_90j']:.0%} en moyenne sur 90 jours : ligne saturée, besoin de trésorerie structurel ?"))
    for i in data["impayes"]:
        if i["statut"] != "Régularisé":
            out.append(("HIGH", f"Impayé en cours : {i['objet']} — {fmt(i['montant'])} DZD, {i['jours_retard']} jours de retard."))
    cr = data["centrale_risques"]
    if len(cr) >= 13:
        a0, a1 = sum(cr[-13]["autres"].values()), sum(cr[-1]["autres"].values())
        b1 = sum(cr[-1]["bnp"].values())
        if a0 and a1 / a0 - 1 > 0.25:
            out.append(("MEDIUM", f"Endettement auprès des autres banques en hausse de {a1 / a0 - 1:.0%} sur 12 mois "
                                  f"(Centrale des risques) ; nombre de banques : {cr[-13]['nb_banques']} → {cr[-1]['nb_banques']}."))
        if a1 + b1:
            out.append(("INFO", f"Part de BNP Paribas El Djazaïr dans l'endettement déclaré : {b1 / (a1 + b1):.0%}."))
    for gq in data["garanties"]:
        if gq.get("date_expertise") and (date.fromisoformat(data["arrete"]) - date.fromisoformat(gq["date_expertise"])).days > 3 * 365:
            out.append(("MEDIUM", f"{gq['libelle']} : expertise de plus de 3 ans ({gq['date_expertise']}) — réévaluation à demander."))
    rv = data["client"].get("derniere_revue")
    if rv and (date.fromisoformat(data["arrete"]) - date.fromisoformat(rv)).days > 365:
        out.append(("MEDIUM", f"Revue annuelle échue (dernière revue le {rv})."))
    if fin:
        y = max(fin); d = fin[y]
        if d.get("rn") is not None and d["rn"] < 0:
            out.append(("HIGH", f"Résultat net {y} négatif : {fmt(d['rn'])} DZD."))
        if d.get("r_dfin_ebe") and d["r_dfin_ebe"] > 4:
            out.append(("MEDIUM", f"Dettes financières / EBE {y} = {d['r_dfin_ebe']:.1f} (seuil de vigilance 4)."))
    order = {"HIGH": 0, "MEDIUM": 1, "INFO": 2}
    return sorted(out, key=lambda x: order.get(x[0], 3))


def fmt(v, dec=0):
    if v is None:
        return "—"
    s = f"{v:,.{dec}f}".replace(",", " ").replace(".", ",")
    return "0" if s in ("-0",) else s


# ---------------------------------------------------------------------------
# RWA — approche standard européenne (CRR / CRR3), version simplifiée pour la démonstration
# ---------------------------------------------------------------------------
RWA_DEFAULTS = {"rw_corporate": 1.00, "rw_defaut": 1.50, "rw_banque": 0.50, "rw_immo_com": 0.60, "quotite_immo": 0.55,
                "ccf_engagement": 0.40, "ccf_revocable": 0.10, "ratio_fp": 0.08, "facteur_pme": False, "jours_defaut": 90}


def rwa(facilites, garanties, impayes=None, params=None, limits=None, usages=None):
    """Calcule EAD, protections et RWA par ligne. limits / usages permettent de simuler une proposition."""
    P = dict(RWA_DEFAULTS, **(params or {}))
    rows, alloc = [], {g["id"]: (g.get("valeur") or g.get("montant") or 0.0) for g in garanties}
    defaut = {i["ligne"] for i in (impayes or []) if i.get("statut") != "Régularisé" and (i.get("jours_retard") or 0) > P["jours_defaut"]}
    for f in facilites:
        t = TYPES[f["type"]]
        L = (limits or {}).get(f["id"], f["autorisation"]) or 0.0
        D = (usages or {}).get(f["id"], f["utilisation"]) or 0.0
        D = min(D, max(L, D))
        U = max(L - D, 0.0)
        ccf_u = P["ccf_revocable"] if t.get("revocable") else P["ccf_engagement"]
        if t.get("amortissable"):
            U, ccf_u = 0.0, 0.0                                   # prêt décaissé : pas d'engagement non tiré
        if t["nature"] == "signature":
            ccf_d = t["ccf_sig"]
            ccf_u = min(ccf_u, ccf_d)
        else:
            ccf_d = 1.0
        ead = D * ccf_d + U * ccf_u
        rw_cp = P["rw_defaut"] if f["id"] in defaut else P["rw_corporate"]
        rest, cash, gar, immo, parts = ead, 0.0, 0.0, 0.0, []
        for g in garanties:
            if f["id"] not in (g.get("lignes") or []) or CRM.get(g["type"]) is None or rest <= 0:
                continue
            avail = alloc.get(g["id"], 0.0)
            if CRM[g["type"]] == "immobilier":
                avail = min(avail, (g.get("valeur") or 0.0) * P["quotite_immo"])
            use = min(avail, rest)
            if use <= 0:
                continue
            alloc[g["id"]] -= use if CRM[g["type"]] != "immobilier" else use / P["quotite_immo"]
            rest -= use
            if CRM[g["type"]] == "cash":
                cash += use
            elif CRM[g["type"]] == "garantie":
                gar += use
            else:
                immo += use
        r = gar * P["rw_banque"] + immo * P["rw_immo_com"] + rest * rw_cp
        if P.get("facteur_pme"):
            r *= 0.7619
        rows.append({"id": f["id"], "libelle": f["libelle"], "nature": t["nature"], "autorisation": L, "utilisation": D, "non_tire": U,
                     "ccf_tire": ccf_d, "ccf_non_tire": ccf_u, "ead": ead, "cash": cash, "garantie_bancaire": gar, "immobilier": immo,
                     "non_couvert": rest, "rw_contrepartie": rw_cp, "rwa": r, "densite": r / ead if ead else None,
                     "fonds_propres": r * P["ratio_fp"], "defaut": f["id"] in defaut})
    tot = {k: sum(x[k] for x in rows) for k in ("autorisation", "utilisation", "ead", "cash", "garantie_bancaire", "immobilier", "non_couvert", "rwa", "fonds_propres")}
    tot["densite"] = tot["rwa"] / tot["ead"] if tot["ead"] else None
    return rows, tot, P


# ---------------------------------------------------------------------------
# Proposition de crédit (aide à la décision, règles indicatives paramétrables)
# ---------------------------------------------------------------------------
PROP_DEFAULTS = {"jours_ca_fc": 15, "quotite_escompte": 0.60, "quotite_stocks": 0.50, "part_import": 0.35, "mois_import": 3,
                 "pct_ca_cautions": 0.05, "dfin_ebe_max": 3.5, "gearing_max": 1.2, "taux_utilisation_proj": 0.75,
                 "besoin_mt": 0.0, "part_leasing": 0.0}

GARANTIES_PROPOSEES = {
    "FC": "Caution personnelle et solidaire des associés ; domiciliation des recettes",
    "AMC": "Nantissement des marchandises financées (magasin sous douane ou tiers détenteur)",
    "ESC": "Endos des effets ; plafond par tiré ; domiciliation des encaissements",
    "LC": "Provision de 10 à 30 % selon le fournisseur ; nantissement des marchandises importées",
    "CAU": "Contre-garantie ou provision selon le marché ; cession des créances du marché",
    "CMT": "Hypothèque 1er rang couvrant au moins 120 % ; nantissement du matériel financé ; assurance",
    "LEA": "Propriété du bien financé (crédit-bail) ; caution des associés",
}


def proposal(fin, data, params=None, nouveau_client=False):
    """Lignes proposées à partir du dernier exercice : [{id, actuel, propose, decision, justification, garantie}], indicateurs."""
    P = dict(PROP_DEFAULTS, **(params or {}))
    if not fin:
        return [], {"message": "Aucun état financier : extraire une liasse ou saisir les données."}
    y = max(fin); d = fin[y]
    z = lambda v: v or 0.0
    ca, ebe, fp, dfin = z(d["ca"]), z(d["ebe"]), z(d["fp"]), z(d["dfin"])
    besoin_cycle = d["bfr"] - d["fr"]
    cur = {} if nouveau_client else {f["id"]: f for f in data["facilites"]}
    prop = {
        "FC": ca * P["jours_ca_fc"] / 360,
        "AMC": z(d["stocks"]) * P["quotite_stocks"],
        "ESC": z(d["clients"]) * P["quotite_escompte"],
        "LC": z(d.get("conso")) * P["part_import"] * P["mois_import"] / 12,
        "CAU": ca * P["pct_ca_cautions"],
    }
    just = {
        "FC": f"{P['jours_ca_fc']} jours de chiffre d'affaires {y}",
        "AMC": f"{P['quotite_stocks']:.0%} des stocks {y}",
        "ESC": f"{P['quotite_escompte']:.0%} des créances clients {y}",
        "LC": f"{P['mois_import']} mois d'achats importés ({P['part_import']:.0%} des consommations {y})",
        "CAU": f"{P['pct_ca_cautions']:.0%} du chiffre d'affaires (à confirmer par le carnet de commandes)",
    }
    # Plafond global des lignes de trésorerie : BFR d'exploitation de fin d'exercice (financement des pointes du cycle)
    ct_ids = ["FC", "AMC", "ESC"]
    ct_tot = sum(prop[k] for k in ct_ids)
    cap = max(d["bfr"], ca * P["jours_ca_fc"] / 360)
    if ct_tot > cap > 0:
        k = cap / ct_tot
        for i in ct_ids:
            prop[i] *= k
            just[i] += f" ; ramené à {k:.0%} pour que le total des lignes de trésorerie reste dans le BFR ({fmt(d['bfr'])} DZD)"
    # Capacité d'endettement moyen terme
    crd = sum(cur[k]["utilisation"] for k in ("CMT", "LEA") if k in cur)
    lim_ebe = P["dfin_ebe_max"] * ebe - dfin
    lim_fp = P["gearing_max"] * fp - dfin
    capa = max(0.0, min(lim_ebe, lim_fp)) if ebe > 0 and fp > 0 else 0.0
    demande = max(0.0, P["besoin_mt"])
    accorde = min(demande, capa)
    new_lea, new_cmt = accorde * P["part_leasing"], accorde * (1 - P["part_leasing"])
    prop["CMT"] = (cur["CMT"]["utilisation"] if "CMT" in cur else 0.0) + new_cmt
    prop["LEA"] = (cur["LEA"]["utilisation"] if "LEA" in cur else 0.0) + new_lea
    regle = f"dettes financières / EBE ≤ {P['dfin_ebe_max']} et gearing ≤ {P['gearing_max']}"
    if demande:
        just["CMT"] = (f"Capital restant dû + {fmt(new_cmt)} DZD de nouveau financement (demande {fmt(demande)} DZD, "
                       f"capacité résiduelle {fmt(capa)} DZD : {regle})" + (" — demande plafonnée à la capacité" if demande > capa else ""))
        just["LEA"] = f"Encours + {fmt(new_lea)} DZD ({P['part_leasing']:.0%} de la demande en crédit-bail)"
    else:
        just["CMT"] = f"Pas de nouvelle demande : capital restant dû (capacité résiduelle {fmt(capa)} DZD : {regle})"
        just["LEA"] = "Pas de nouvelle demande : encours restant"
    malus = []
    if z(d["rn"]) < 0:
        malus.append("résultat net négatif")
    if fp <= 0:
        malus.append("capitaux propres négatifs")
    if d.get("capital") and fp < d["capital"] / 4:
        malus.append("capitaux propres < 1/4 du capital")
    lines = []
    for k, t in TYPES.items():
        p = _r(prop.get(k, 0.0), 1e6)
        if malus and k not in ("CMT", "LEA"):
            p = _r(p * 0.7, 1e6)
        a = cur[k]["autorisation"] if k in cur else 0.0
        if a == 0 and p == 0:
            continue
        if k in ("CMT", "LEA") and k in cur:
            a = _r(cur[k]["utilisation"], 1e6)          # amortissable : on compare au capital restant dû
        var = (p - a) / a if a else None
        dec = ("Nouvelle ligne" if not a else "Renouvellement" if abs(var) < 0.10 else "Augmentation" if var > 0 else "Réduction")
        if k in ("CMT", "LEA") and a and abs(var) < 0.10:
            dec = "Maintien (amortissement en cours)"
        if p == 0 and a:
            dec = "Non-renouvellement"
        lines.append({"id": k, "libelle": t["lib"], "actuel": a, "propose": p, "variation": var, "decision": dec,
                      "justification": just.get(k, "") + (" ; abattement de 30 % (" + ", ".join(malus) + ")" if malus and k not in ("CMT", "LEA") else ""),
                      "garantie": GARANTIES_PROPOSEES[k]})
    ind = {"exercice": y, "ca": ca, "ebe": ebe, "fp": fp, "dfin": dfin, "bfr": d["bfr"], "fr": d["fr"], "besoin_cycle": besoin_cycle,
           "capacite_mt": capa, "crd_mt_leasing": crd, "malus": malus}
    return lines, ind


# ---------------------------------------------------------------------------
# Questions Risques → commercial (générées à partir des données)
# ---------------------------------------------------------------------------
def questions(fin, data):
    q = []

    def add(theme, texte, pourquoi, prio="Moyenne"):
        q.append({"id": hashlib.md5(texte.encode()).hexdigest()[:8], "theme": theme, "question": texte, "pourquoi": pourquoi,
                  "priorite": prio, "source": "auto"})
    ys = sorted(fin)
    if ys:
        y = ys[-1]; d = fin[y]
        if len(ys) >= 2 and fin[ys[-2]].get("ca"):
            v = (d["ca"] or 0) / fin[ys[-2]]["ca"] - 1
            if abs(v) >= 0.10:
                add("Activité", f"Le chiffre d'affaires {y} évolue de {v:+.0%} par rapport à {ys[-2]}. Quelle est la part liée aux volumes, aux prix, aux nouveaux clients ou marchés ?",
                    f"CA {ys[-2]} : {fmt(fin[ys[-2]]['ca'])} → {y} : {fmt(d['ca'])} DZD", "Haute" if abs(v) > 0.25 else "Moyenne")
        if len(ys) >= 2 and d.get("r_marge_ebe") is not None and fin[ys[-2]].get("r_marge_ebe") is not None:
            dm = d["r_marge_ebe"] - fin[ys[-2]]["r_marge_ebe"]
            if dm < -0.02:
                add("Rentabilité", f"La marge d'EBE recule de {abs(dm) * 100:.1f} points. Quelles charges ont augmenté (matières, personnel, sous-traitance) et sont-elles répercutables sur les prix ?",
                    f"Marge d'EBE {fin[ys[-2]]['r_marge_ebe']:.1%} → {d['r_marge_ebe']:.1%}", "Haute")
        if d.get("rn") is not None and d["rn"] < 0:
            add("Rentabilité", "Le résultat net est négatif. Quelles en sont les causes et quel est le plan de retour à l'équilibre (calendrier, mesures) ?",
                f"Résultat net {y} : {fmt(d['rn'])} DZD", "Haute")
        if d.get("capital") and d.get("fp") is not None and d["fp"] < d["capital"] / 4:
            add("Structure", "Les capitaux propres sont inférieurs au quart du capital social. Quelles décisions les associés ont-ils prises (recapitalisation, AG) ?",
                f"FP {fmt(d['fp'])} DZD / capital {fmt(d['capital'])} DZD", "Haute")
        if d.get("r_dfin_ebe") and d["r_dfin_ebe"] > 3.5:
            add("Endettement", "Le niveau d'endettement est élevé au regard de l'EBE. Quel est l'échéancier de remboursement des dettes financières, toutes banques confondues ?",
                f"Dettes financières / EBE = {d['r_dfin_ebe']:.1f}", "Haute")
        if d.get("j_clients") and d["j_clients"] > 90:
            add("Cycle d'exploitation", "Le délai de paiement des clients dépasse 90 jours. Qui sont les principaux clients, quelle part est publique, y a-t-il des créances douteuses ou litigieuses ?",
                f"Délai clients {d['j_clients']:.0f} jours de CA", "Haute" if d["j_clients"] > 120 else "Moyenne")
        if len(ys) >= 2 and fin[ys[-2]].get("j_stocks") and d.get("j_stocks") and d["j_stocks"] - fin[ys[-2]]["j_stocks"] > 15:
            add("Cycle d'exploitation", "Les stocks augmentent plus vite que l'activité. S'agit-il d'un stock de précaution, de produits à rotation lente ou d'invendus ?",
                f"Stocks {fin[ys[-2]]['j_stocks']:.0f} → {d['j_stocks']:.0f} jours de CA")
        if d.get("treso") is not None and d["treso"] < 0:
            add("Trésorerie", "La trésorerie nette est négative en fin d'exercice. Comment le client finance-t-il ses pics de besoin et à quelles banques fait-il appel ?",
                f"Trésorerie nette {fmt(d['treso'])} DZD")
        add("Activité", "Quel est le carnet de commandes à date et sa couverture en mois de chiffre d'affaires ? Joindre la liste des principaux marchés.",
            "Donnée absente des états financiers", "Moyenne")
        add("Situation intermédiaire", f"Le client peut-il fournir une situation comptable de l'exercice en cours ({y + 1}) ? Comment évoluent le CA et la marge depuis janvier ?",
            "Dernier exercice disponible : " + str(y), "Moyenne")
    for f in data.get("facilites", []):
        s = usage_stats(f)
        if s and s.get("jours_depassement_90j"):
            add("Fonctionnement du compte", f"{f['libelle']} : {s['jours_depassement_90j']} jours de dépassement sur 90 jours. Quelle en est la cause et comment le client compte-t-il les éviter ?",
                f"Pointe de {fmt(s['depassement_max'])} DZD au-delà de l'autorisation", "Haute")
    for i in data.get("impayes", []):
        if i["statut"] != "Régularisé":
            add("Incidents", f"Impayé en cours sur « {i['objet']} » ({fmt(i['montant'])} DZD, {i['jours_retard']} jours). Date prévue de régularisation ?",
                "Impayé non régularisé", "Haute")
    cr = data.get("centrale_risques") or []
    if len(cr) >= 13:
        a0, a1 = sum(cr[-13]["autres"].values()), sum(cr[-1]["autres"].values())
        if a0 and a1 / a0 - 1 > 0.25:
            add("Autres banques", "La Centrale des risques montre une hausse de l'endettement auprès d'autres banques. Quels financements ont été obtenus, pour quel objet et avec quelles garanties ?",
                f"Autres banques : {fmt(a0)} → {fmt(a1)} DZD sur 12 mois", "Haute")
    for g in data.get("garanties", []):
        if g.get("date_expertise") and (date.fromisoformat(data["arrete"]) - date.fromisoformat(g["date_expertise"])).days > 3 * 365:
            add("Garanties", f"{g['libelle']} : l'expertise date de plus de 3 ans. Le client accepte-t-il une nouvelle expertise ?",
                f"Expertise du {g['date_expertise']}")
    add("Conformité", "Les attestations fiscales et parafiscales (CNAS / CASNOS) sont-elles à jour ? Y a-t-il des litiges ou contentieux en cours ?",
        "Pièces du dossier de crédit", "Basse")
    add("Gouvernance", "Y a-t-il eu des changements dans l'actionnariat, la gérance ou les sociétés liées depuis la dernière revue ?",
        "Mise à jour de la fiche client", "Basse")
    order = {"Haute": 0, "Moyenne": 1, "Basse": 2}
    return sorted(q, key=lambda x: order[x["priorite"]])
