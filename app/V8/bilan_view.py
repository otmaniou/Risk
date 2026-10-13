"""Ya-Risk — vue « Bilan » (Actif / Passif / TCR) fidèle aux feuilles Saisie du modèle ANALYSTE V20.

Lit le JSON canonique V29d (pages[].donnees.{ACTIF,PASSIF,TCR}, montants en DZD),
recalcule les lignes-formules comme le modèle Excel et compare au montant imprimé
sur la liasse. Les valeurs observées ne sont jamais remplacées : l'écart est signalé.
"""
import html
import re

# ---------------------------------------------------------------------------
# Seuils V28/V29 (écarts absolus en DZD) — identiques au notebook V29d
# ---------------------------------------------------------------------------
ALERT_MIN_DZD = 1_000.0
ALERT_MEDIUM_DZD = 10_000.0
ALERT_HIGH_DZD = 1_000_000.0
LEVEL_RANK = {"OK": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


def ecart_level(gap):
    a = abs(float(gap or 0.0))
    if a < ALERT_MIN_DZD:
        return "OK"
    if a < ALERT_MEDIUM_DZD:
        return "LOW"
    if a < ALERT_HIGH_DZD:
        return "MEDIUM"
    return "HIGH"


# ---------------------------------------------------------------------------
# Mise en page : lignes et libellés repris des feuilles « Saisie actif / passif / TCR »
# style : sec (section C6E5D4), sub (sous-total EAF5EF), tot (total 00573F), row (détail)
# ---------------------------------------------------------------------------
ACTIF_LAYOUT = [
    ("ACTIFS NON COURANTS", "_anc", "sec"),
    ("Ecart d’acquisition – goodwill positif ou négatif", "ecarts_acquisition_goodwill", "row"),
    ("Immobilisations incorporelles", "immobilisations_incorporelles", "row"),
    ("Immobilisations corporelles", "immobilisations_corporelles", "sub"),
    ("Terrains", "terrains", "row"),
    ("Bâtiments", "batiments", "row"),
    ("Autres immobilisations corporelles", "autres_immobilisations_corporelles", "row"),
    ("Immobilisations en concession", "immobilisations_en_concession", "row"),
    ("Immobilisations en cours", "immobilisations_en_cours", "row"),
    ("Immobilisations financières", "immobilisations_financieres", "sub"),
    ("Titres mis en équivalence", "titres_mis_en_equivalence", "row"),
    ("Autres participations et créances rattachées", "autres_participations_creances", "row"),
    ("Autres titres immobilisés", "autres_titres_immobilises", "row"),
    ("Prêts et autres actifs financiers non courants", "prets_actifs_financiers_non_courants", "row"),
    ("Impôts différés actif", "impots_differes_actif", "row"),
    ("TOTAL ACTIF NON COURANT", "total_actif_non_courant", "tot"),
    ("ACTIFS COURANTS", "_ac", "sec"),
    ("Stocks et encours", "stocks_encours", "row"),
    ("Créances et emplois assimilés", "creances_emplois_assimiles", "sub"),
    ("Clients", "clients", "row"),
    ("Autres débiteurs", "autres_debiteurs", "row"),
    ("Impôts et assimilés", "impots_assimiles_actif", "row"),
    ("Autres créances et emplois assimilés", "autres_creances_assimiles", "row"),
    ("Disponibilités et assimilés", "disponibilites_assimiles", "sub"),
    ("Placements et autres actifs financiers courants", "placements_financiers_courants", "row"),
    ("Trésorerie", "tresorerie_actif", "row"),
    ("TOTAL ACTIF COURANT", "total_actif_courant", "tot"),
    ("TOTAL GENERAL ACTIF", "total_general_actif", "tot"),
]
# Formules du modèle V20 (Saisie actif) — composantes signées
ACTIF_FORMULAS = {
    # Règle Ya-Risk : actif non courant = goodwill + incorporelles + corporelles + financières,
    # immobilisations corporelles = terrains + bâtiments + autres + concession + en cours
    "_anc": [("ecarts_acquisition_goodwill", 1), ("immobilisations_incorporelles", 1), ("immobilisations_corporelles", 1),
             ("immobilisations_financieres", 1)],
    "immobilisations_corporelles": [("terrains", 1), ("batiments", 1), ("autres_immobilisations_corporelles", 1),
                                    ("immobilisations_en_concession", 1), ("immobilisations_en_cours", 1)],
    "immobilisations_financieres": [("titres_mis_en_equivalence", 1), ("autres_participations_creances", 1),
                                    ("autres_titres_immobilises", 1), ("prets_actifs_financiers_non_courants", 1),
                                    ("impots_differes_actif", 1)],
    "total_actif_non_courant": [("_anc", 1)],
    "_ac": [("stocks_encours", 1), ("creances_emplois_assimiles", 1), ("disponibilites_assimiles", 1)],
    "creances_emplois_assimiles": [("clients", 1), ("autres_debiteurs", 1), ("impots_assimiles_actif", 1),
                                   ("autres_creances_assimiles", 1)],
    "disponibilites_assimiles": [("placements_financiers_courants", 1), ("tresorerie_actif", 1)],
    "total_actif_courant": [("_ac", 1)],
    "total_general_actif": [("total_actif_non_courant", 1), ("total_actif_courant", 1)],
}

PASSIF_LAYOUT = [
    ("CAPITAUX PROPRES :", "_cp", "sec"),
    ("Capital émis", "capital_emis", "row"),
    ("Capital non appelé", "capital_non_appele", "row"),
    ("Primes et réserves - Réserves consolidées (1)", "primes_reserves", "row"),
    ("Ecarts de réévaluation", "ecart_reevaluation", "row"),
    ("Ecart d’équivalence (1)", "ecart_equivalence", "row"),
    ("Résultat net - Résultat net part du groupe (1)", "resultat_net_passif", "row"),
    ("Autres capitaux propres – Report à nouveau", "report_a_nouveau", "row"),
    ("Part de la société consolidante (1)", "part_societe_consolidante", "row"),
    ("Part des minoritaires (1)", "part_minoritaires", "row"),
    ("TOTAL I (KDZD)", "total_capitaux_propres", "tot"),
    ("PASSIFS NON-COURANTS :", "_pnc", "sec"),
    ("Emprunts et dettes financières", "emprunts_dettes_financieres", "row"),
    ("Impôts (différés et provisionnés)", "impots_differes_provisionnes", "row"),
    ("Autres dettes non courantes", "autres_dettes_non_courantes", "row"),
    ("Provisions et produits constatés d’avance", "provisions_produits_avance", "row"),
    ("TOTAL II (KDZD)", "total_passifs_non_courants", "tot"),
    ("PASSIFS COURANTS :", "_pc", "sec"),
    ("Fournisseurs et comptes rattachés", "fournisseurs_rattaches", "row"),
    ("Impôts", "impots_passif", "row"),
    ("Autres dettes", "autres_dettes", "sub"),
    ("Trésorerie Passif", "tresorerie_passif", "row"),
    ("TOTAL III (KDZD)", "total_passifs_courants", "tot"),
    ("TOTAL PASSIF (I+II+III) (KDZD)", "total_general_passif", "tot"),
]
PASSIF_FORMULAS = {
    "_cp": [("capital_emis", 1), ("capital_non_appele", -1), ("primes_reserves", 1), ("ecart_reevaluation", 1),
            ("ecart_equivalence", 1), ("resultat_net_passif", 1), ("report_a_nouveau", 1)],
    "total_capitaux_propres": [("_cp", 1)],
    "_pnc": [("emprunts_dettes_financieres", 1), ("impots_differes_provisionnes", 1),
             ("autres_dettes_non_courantes", 1), ("provisions_produits_avance", 1)],
    "total_passifs_non_courants": [("_pnc", 1)],
    "_pc": [("fournisseurs_rattaches", 1), ("impots_passif", 1), ("autres_dettes", 1), ("tresorerie_passif", 1)],
    "total_passifs_courants": [("_pc", 1)],
    "total_general_passif": [("total_capitaux_propres", 1), ("total_passifs_non_courants", 1),
                             ("total_passifs_courants", 1)],
}

# TCR : (libellé colonne C, libellé colonne D, row_id, style). Groupes C fusionnés comme dans la feuille.
TCR_LAYOUT = [
    ("Ventes de marchandises", None, "ventes_marchandises", "row"),
    ("Production vendue", "Produits fabriqués", "produits_fabriques", "row"),
    (None, "Prestations de services", "prestations_services", "row"),
    (None, "Vente de travaux", "ventes_travaux", "row"),
    ("Produits annexes", None, "produits_annexes", "row"),
    ("Rabais, remises, ristournes accordés", None, "rabais_remises_ristournes_accordes", "row"),
    ("Chiffre d’affaires net des Rabais, remises, ristournes", None, "chiffre_affaires_net", "sub"),
    ("Production stockée ou déstockée", None, "production_stockee_destockee", "row"),
    ("Production immobilisée", None, "production_immobilisee", "row"),
    ("Subventions d’exploitation", None, "subvention_exploitation", "row"),
    ("I-Production de l’exercice", None, "production_exercice", "sec"),
    ("Achats de marchandises vendues", None, "achats_marchandises_vendues", "row"),
    ("Matières premières", None, "matieres_premieres", "row"),
    ("Autres approvisionnements", None, "autres_approvisionnements", "row"),
    ("Variations des stocks", None, "variation_stocks", "row"),
    ("Achats d’études et de prestations de services", None, "achats_etudes_prestations", "row"),
    ("Autres consommations", None, "autres_consommations", "row"),
    ("Rabais, remises, ristournes obtenus sur achats", None, "rabais_remises_ristournes_obtenus_achats", "row"),
    ("Services extérieurs", "Sous-traitance générale", "sous_traitance_generale", "row"),
    (None, "Locations", "locations", "row"),
    (None, "Entretien, réparations et maintenance", "entretien_reparations", "row"),
    (None, "Primes d'assurances", "primes_assurances", "row"),
    (None, "Personnel extérieur à l’entreprise", "personnel_exterieur", "row"),
    (None, "Rémunération d’intermédiaires et honoraires", "remuneration_intermediaires", "row"),
    (None, "Publicité", "publicite", "row"),
    (None, "Déplacements, missions et réceptions", "deplacements_missions", "row"),
    ("Autres services", None, "autres_services", "row"),
    ("Rabais, remises, ristournes obtenus sur services extérieurs", None,
     "rabais_remises_ristournes_obtenus_services", "row"),
    ("II-Consommations de l’exercice", None, "consommations_exercice", "sec"),
    ("III-Valeur ajoutée d’exploitation (I–II)", None, "valeur_ajoutee_exploitation", "sec"),
    ("", "Charges de personnel", "charges_personnel", "row"),
    ("", "Impôts et taxes et versements assimilés", "impots_taxes_assimiles", "row"),
    ("IV-Excédent brut d’exploitation", None, "excedent_brut_exploitation", "sec"),
    ("Autres produits opérationnels", None, "autres_produits_operationnels", "row"),
    ("Autres charges opérationnelles", None, "autres_charges_operationnelles", "row"),
    ("Dotations aux amortissements", None, "dotations_amortissements", "row"),
    ("Provision", None, "provisions", "row"),
    ("Pertes de valeur", None, "pertes_valeur", "row"),
    ("Reprise sur pertes de valeur et provisions", None, "reprises_pertes_valeur_provisions", "row"),
    ("V-Résultat opérationnel", None, "resultat_operationnel", "sec"),
    ("Produits financiers", None, "produits_financiers", "row"),
    ("Charges financières", None, "charges_financieres", "row"),
    ("VI-Résultat financier", None, "resultat_financier", "sec"),
    ("VII-Résultat ordinaire (V+VI)", None, "resultat_ordinaire", "sec"),
    ("Eléments extraordinaires (produits) (*)", None, "elements_extraordinaires_produits", "row"),
    ("Eléments extraordinaires (Charges) (*)", None, "elements_extraordinaires_charges", "row"),
    ("VIII-Résultat extraordinaire", None, "resultat_extraordinaire", "sec"),
    ("Impôts exigibles sur résultats", None, "impots_exigibles_resultats", "row"),
    ("Impôts différés (variations) sur résultats", None, "impots_differes_resultats", "row"),
    ("IX - RESULTAT NET DE L’EXERCICE", None, "resultat_net_exercice", "tot"),
]
TCR_FORMULAS = {
    "chiffre_affaires_net": ["ventes_marchandises", "produits_fabriques", "prestations_services", "ventes_travaux",
                             "produits_annexes", "rabais_remises_ristournes_accordes"],
    "production_exercice": ["chiffre_affaires_net", "production_stockee_destockee", "production_immobilisee",
                            "subvention_exploitation"],
    "consommations_exercice": ["achats_marchandises_vendues", "matieres_premieres", "autres_approvisionnements",
                               "variation_stocks", "achats_etudes_prestations", "autres_consommations",
                               "rabais_remises_ristournes_obtenus_achats", "sous_traitance_generale", "locations",
                               "entretien_reparations", "primes_assurances", "personnel_exterieur",
                               "remuneration_intermediaires", "publicite", "deplacements_missions", "autres_services",
                               "rabais_remises_ristournes_obtenus_services"],
    "valeur_ajoutee_exploitation": ["production_exercice", "consommations_exercice"],
    "excedent_brut_exploitation": ["valeur_ajoutee_exploitation", "charges_personnel", "impots_taxes_assimiles"],
    "resultat_operationnel": ["excedent_brut_exploitation", "autres_produits_operationnels",
                              "autres_charges_operationnelles", "dotations_amortissements", "provisions",
                              "pertes_valeur", "reprises_pertes_valeur_provisions"],
    "resultat_financier": ["produits_financiers", "charges_financieres"],
    "resultat_ordinaire": ["resultat_operationnel", "resultat_financier"],
    "resultat_extraordinaire": ["elements_extraordinaires_produits", "elements_extraordinaires_charges"],
    "resultat_net_exercice": ["resultat_ordinaire", "resultat_extraordinaire", "impots_exigibles_resultats",
                              "impots_differes_resultats"],
}
# Sens attendu des rubriques TCR (V29) — alerte uniquement, jamais de permutation
TCR_SIDE_RULES = {
    "ventes_marchandises": "CREDIT", "produits_fabriques": "CREDIT", "prestations_services": "CREDIT",
    "ventes_travaux": "CREDIT", "produits_annexes": "CREDIT", "rabais_remises_ristournes_accordes": "DEBIT",
    "production_immobilisee": "CREDIT", "subvention_exploitation": "CREDIT",
    "achats_marchandises_vendues": "DEBIT", "matieres_premieres": "DEBIT", "autres_approvisionnements": "DEBIT",
    "achats_etudes_prestations": "DEBIT", "autres_consommations": "DEBIT",
    "rabais_remises_ristournes_obtenus_achats": "CREDIT", "sous_traitance_generale": "DEBIT", "locations": "DEBIT",
    "entretien_reparations": "DEBIT", "primes_assurances": "DEBIT", "personnel_exterieur": "DEBIT",
    "remuneration_intermediaires": "DEBIT", "publicite": "DEBIT", "deplacements_missions": "DEBIT",
    "autres_services": "DEBIT", "rabais_remises_ristournes_obtenus_services": "CREDIT",
    "charges_personnel": "DEBIT", "impots_taxes_assimiles": "DEBIT",
    "autres_produits_operationnels": "CREDIT", "autres_charges_operationnelles": "DEBIT",
    "dotations_amortissements": "DEBIT", "provisions": "DEBIT", "pertes_valeur": "DEBIT",
    "reprises_pertes_valeur_provisions": "CREDIT", "produits_financiers": "CREDIT", "charges_financieres": "DEBIT",
    "elements_extraordinaires_produits": "CREDIT", "elements_extraordinaires_charges": "DEBIT",
    "impots_exigibles_resultats": "DEBIT",
}

TABLE_LABELS = {"ACTIF": "Actif", "PASSIF": "Passif", "TCR": "TCR"}


def editable_rows(table):
    """(libellé, row_id) des rubriques corrigeables — exclut les lignes de section purement calculées."""
    if table == "ACTIF":
        return [(lbl, rid) for lbl, rid, _ in ACTIF_LAYOUT if not rid.startswith("_")]
    if table == "PASSIF":
        return [(lbl, rid) for lbl, rid, _ in PASSIF_LAYOUT if not rid.startswith("_")]
    return [((d or c), rid) for c, d, rid, _ in TCR_LAYOUT]


def column_options(table, year):
    """(column_id, libellé) des colonnes du JSON V29d pour un état."""
    y1 = f"{year - 1}" if year else "N-1"
    y = f"{year}" if year else "N"
    if table == "ACTIF":
        return [("montant_brut", f"Brut {y}"), ("amortissements_provisions_pertes", f"Amort./prov. {y}"),
                ("net_n", f"Net {y}"), ("net_n1", f"Net {y1}")]
    if table == "PASSIF":
        return [("n", y), ("n1", y1)]
    return [("n_debit", f"Débit {y}"), ("n_credit", f"Crédit {y}"), ("n1_debit", f"Débit {y1}"),
            ("n1_credit", f"Crédit {y1}")]


# ---------------------------------------------------------------------------
# Lecture du JSON V29d
# ---------------------------------------------------------------------------
def _num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return parse_amount(v)


def parse_amount(v):
    """Montant saisi (« 1 234 567,89 », « (12 000) », « -5000 ») -> float DZD, None si vide."""
    if v is None:
        return None
    s = str(v).strip().replace(" ", " ").replace(" ", " ")
    if not s or s.lower() in {"null", "none", "-", "—"}:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(" ", "").replace("DZD", "").replace("DA", "")
    if "," in s and "." not in s and len(s.rsplit(",", 1)[-1]) <= 2:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    s = re.sub(r"[^0-9.\-+]", "", s)
    if not s:
        raise ValueError("montant illisible")
    x = float(s)
    return -x if neg else x


def is_v29d(doc):
    return isinstance(doc, dict) and (isinstance(doc.get("pages"), list) or
                                      any(isinstance(doc.get(t), dict) for t in ("ACTIF", "PASSIF", "TCR")))


def index_doc(doc):
    """{table: {row_id: {col: valeur DZD}}} fusionné sur toutes les pages (même logique que le notebook)."""
    idx = {"ACTIF": {}, "PASSIF": {}, "TCR": {}}
    sources = {}
    blocks = []
    for p in doc.get("pages") or []:
        if isinstance(p, dict) and isinstance(p.get("donnees"), dict):
            blocks.append((p.get("numero_page_scannee"), p["donnees"]))
    if not blocks:
        blocks.append((None, {t: doc[t] for t in ("ACTIF", "PASSIF", "TCR") if isinstance(doc.get(t), dict)}))
    for page_no, donnees in blocks:
        for table, rows in donnees.items():
            if table not in idx or not isinstance(rows, dict):
                continue
            for rid, vals in rows.items():
                if not isinstance(vals, dict):
                    continue
                for col, v in vals.items():
                    n = _num(v) if not isinstance(v, str) else _safe_parse(v)
                    if n is None:
                        continue
                    idx[table].setdefault(rid, {})[col] = n
                    if page_no:
                        sources[(table, rid, col)] = page_no
    return idx, sources


def _safe_parse(v):
    try:
        return parse_amount(v)
    except ValueError:
        return None


def table_pages(doc, table):
    pages = []
    for p in doc.get("pages") or []:
        if isinstance(p, dict) and table in ((p.get("donnees") or {})):
            n = p.get("numero_page_scannee")
            if n and n not in pages:
                pages.append(n)
    return pages


def doc_year(doc, fallback=None):
    ident = doc.get("identite") or {}
    y = ident.get("annee")
    try:
        return int(y) if y else fallback
    except (TypeError, ValueError):
        return fallback


# ---------------------------------------------------------------------------
# Moteur de calcul « comme Excel » + contrôles
# ---------------------------------------------------------------------------
class Cell:
    __slots__ = ("value", "observed", "computed", "kind", "level", "note", "page", "corrected")

    def __init__(self, value=None, observed=None, computed=None, kind="input", level="OK", note="", page=None):
        self.value, self.observed, self.computed = value, observed, computed
        self.kind, self.level, self.note, self.page = kind, level, note, page
        self.corrected = None


def _compare(cell, label_calc="Calculé (formule V20)"):
    if cell.observed is not None and cell.computed is not None:
        gap = cell.observed - cell.computed
        cell.level = ecart_level(gap)
        if cell.level != "OK":
            cell.note = (f"Liasse : {fmt_dzd(cell.observed)} DZD · {label_calc} : {fmt_dzd(cell.computed)} DZD"
                         f" · Écart : {fmt_dzd(gap)} DZD")


def compute_balance(table, rows, sources):
    """ACTIF / PASSIF : renvoie {(row_id, col): Cell}."""
    formulas = ACTIF_FORMULAS if table == "ACTIF" else PASSIF_FORMULAS
    layout = ACTIF_LAYOUT if table == "ACTIF" else PASSIF_LAYOUT
    cols = ["montant_brut", "amortissements_provisions_pertes", "net_n", "net_n1"] if table == "ACTIF" else ["n", "n1"]
    out = {}

    def leaf(rid, col):
        key = (rid, col)
        if key in out:
            return out[key].value
        obs = (rows.get(rid) or {}).get(col)
        c = Cell(value=obs, observed=obs, kind="input", page=sources.get((table, rid, col)))
        if table == "ACTIF" and col == "net_n":
            # Feuille V20 : Net = Brut − Amortissements (formule) ; le Net imprimé devient un contrôle.
            brut = (rows.get(rid) or {}).get("montant_brut")
            amort = (rows.get(rid) or {}).get("amortissements_provisions_pertes")
            if brut is not None or amort is not None:
                c.kind = "formula"
                c.computed = (brut or 0.0) - (amort or 0.0)
                c.value = c.computed
                _compare(c, "Brut − Amort.")
        out[key] = c
        return c.value

    def val(rid, col):
        if rid not in formulas:
            return leaf(rid, col)
        key = (rid, col)
        if key in out:
            return out[key].value
        parts = [(val(r, col), s) for r, s in formulas[rid]]
        present = [v * s for v, s in parts if v is not None]
        obs = (rows.get(rid) or {}).get(col) if not rid.startswith("_") else None
        c = Cell(observed=obs, kind="formula", page=sources.get((table, rid, col)))
        if present:
            c.computed = sum(present)
            c.value = c.computed
            _compare(c)
        else:
            c.value = obs
            if obs is not None:
                c.note = "Composantes absentes : montant imprimé repris tel quel."
        out[key] = c
        return c.value

    for _, rid, _ in layout:
        for col in cols:
            val(rid, col)
    return out


def tcr_net(vals, period):
    d = vals.get(period + "_debit")
    c = vals.get(period + "_credit")
    if d is None and c is None:
        return None
    return (c or 0.0) - (d or 0.0)


def compute_tcr(rows, sources):
    """TCR : {(row_id, period): Cell} où value = solde net (crédit − débit) ; + positions débit/crédit."""
    out = {}

    def net(rid, period):
        key = (rid, period)
        if key in out:
            return out[key].value
        vals = rows.get(rid) or {}
        obs = tcr_net(vals, period)
        page = sources.get(("TCR", rid, period + "_debit")) or sources.get(("TCR", rid, period + "_credit"))
        if rid in TCR_FORMULAS:
            parts = [net(r, period) for r in TCR_FORMULAS[rid]]
            present = [p for p in parts if p is not None]
            c = Cell(observed=obs, kind="formula", page=page)
            if present:
                c.computed = sum(present)
                c.value = c.computed
                _compare(c)
                # V29 : ligne calculée imprimée du mauvais côté par rapport au signe recalculé
                if abs(c.computed) > 1e-9:
                    wrong = vals.get(period + ("_debit" if c.computed > 0 else "_credit"))
                    if wrong is not None and abs(wrong) > 1e-9:
                        c.level = "HIGH"
                        c.note = (c.note + " · " if c.note else "") + (
                            "Montant imprimé du côté " + ("DÉBIT" if c.computed > 0 else "CRÉDIT") +
                            " alors que le solde recalculé est " + ("créditeur" if c.computed > 0 else "débiteur") + ".")
            else:
                c.value = obs
        else:
            c = Cell(value=obs, observed=obs, kind="input", page=page)
            expected = TCR_SIDE_RULES.get(rid)
            if expected:
                wrong = vals.get(period + ("_credit" if expected == "DEBIT" else "_debit"))
                if wrong is not None and abs(wrong) > 1e-9:
                    c.level = "HIGH"
                    c.note = (f"Montant {fmt_dzd(wrong)} DZD au "
                              f"{'CRÉDIT' if expected == 'DEBIT' else 'DÉBIT'} ; sens attendu : {expected}. "
                              "Aucune permutation automatique.")
        out[key] = c
        return c.value

    for _, _, rid, _ in TCR_LAYOUT:
        for period in ("n", "n1"):
            net(rid, period)
    return out


def build_model(doc, year=None, corrections=None):
    """Calcule les trois états + contrôles croisés + liste d'alertes."""
    idx, sources = index_doc(doc)
    year = doc_year(doc, year)
    actif = compute_balance("ACTIF", idx["ACTIF"], sources)
    passif = compute_balance("PASSIF", idx["PASSIF"], sources)
    tcr = compute_tcr(idx["TCR"], sources)

    corr_map = {}
    for c in corrections or []:
        fid = c.get("champ") or ""
        corr_map[fid] = c
    for table, cells in (("ACTIF", actif), ("PASSIF", passif)):
        for (rid, col), cell in cells.items():
            cell.corrected = corr_map.get(f"{table}.{rid}.{col}")
    for (rid, period), cell in tcr.items():
        cell.corrected = corr_map.get(f"TCR.{rid}.{period}_debit") or corr_map.get(f"TCR.{rid}.{period}_credit")

    # Contrôles croisés (même esprit que la ligne 29 de Saisie passif et les CROSS du notebook)
    cross = []
    for col_a, col_p, period, y in (("net_n", "n", "n", year), ("net_n1", "n1", "n1", year - 1 if year else None)):
        a = actif[("total_general_actif", col_a)].value
        p = passif[("total_general_passif", col_p)].value
        if a is not None and p is not None:
            cross.append({"controle": "Total actif = Total passif", "exercice": y, "a": a, "b": p,
                          "ecart": a - p, "level": ecart_level(a - p)})
        r_tcr = tcr[("resultat_net_exercice", period)].value
        r_pas = passif[("resultat_net_passif", col_p)].value
        if r_tcr is not None and r_pas is not None:
            cross.append({"controle": "Résultat TCR = Résultat net au passif", "exercice": y, "a": r_tcr, "b": r_pas,
                          "ecart": r_tcr - r_pas, "level": ecart_level(r_tcr - r_pas)})

    alerts = []
    labels = {rid: lbl for lbl, rid, _ in ACTIF_LAYOUT}
    for (rid, col), c in actif.items():
        if c.level != "OK":
            alerts.append(("Actif", labels.get(rid, rid), _col_label("ACTIF", col, year), c))
    labels = {rid: lbl for lbl, rid, _ in PASSIF_LAYOUT}
    for (rid, col), c in passif.items():
        if c.level != "OK":
            alerts.append(("Passif", labels.get(rid, rid), _col_label("PASSIF", col, year), c))
    labels = {rid: (d or cl) for cl, d, rid, _ in TCR_LAYOUT}
    for (rid, period), c in tcr.items():
        if c.level != "OK":
            alerts.append(("TCR", labels.get(rid, rid), str(year if period == "n" else (year - 1 if year else "N-1")), c))

    return {"year": year, "idx": idx, "actif": actif, "passif": passif, "tcr": tcr, "cross": cross, "alerts": alerts}


def _col_label(table, col, year):
    return dict(column_options(table, year)).get(col, col)


def fmt_dzd(v):
    if v is None:
        return ""
    return f"{v:,.0f}".replace(",", " ")


def fmt(v, unit):
    if v is None:
        return ""
    x = v / 1000.0 if unit == "KDZD" else v
    s = f"{x:,.0f}".replace(",", " ")
    return "0" if s in ("-0",) else s


# ---------------------------------------------------------------------------
# Correction d'une valeur dans le JSON V29d (copie de travail)
# ---------------------------------------------------------------------------
TCR_P2_ROWS = {"autres_produits_operationnels", "autres_charges_operationnelles", "dotations_amortissements",
               "provisions", "pertes_valeur", "reprises_pertes_valeur_provisions", "resultat_operationnel",
               "produits_financiers", "charges_financieres", "resultat_financier", "resultat_ordinaire",
               "elements_extraordinaires_produits", "elements_extraordinaires_charges", "resultat_extraordinaire",
               "impots_exigibles_resultats", "impots_differes_resultats", "resultat_net_exercice"}


def get_value(doc, table, rid, col):
    idx, _ = index_doc(doc)
    return (idx.get(table, {}).get(rid) or {}).get(col)


def set_value(doc, table, rid, col, value):
    """Écrit value (DZD ou None) dans la page qui porte la rubrique ; met à jour les observations."""
    pages = [p for p in (doc.get("pages") or []) if isinstance(p, dict)]
    target = None
    if pages:
        holders = [p for p in pages if rid in ((p.get("donnees") or {}).get(table) or {})]
        if holders:
            target = holders[-1]
        else:
            cands = [p for p in pages if table in (p.get("donnees") or {})]
            if table == "TCR" and len(cands) > 1:
                want = "TCR_P2" if rid in TCR_P2_ROWS else "TCR_P1"
                pref = [p for p in cands if (p.get("classification") or {}).get("page_template") == want]
                cands = pref or cands
            target = cands[0] if cands else None
        if target is None:
            target = {"page_id": "correction_manuelle", "numero_page_scannee": None,
                      "classification": {"page_template": table, "types": [table], "page_utile": True},
                      "donnees": {table: {}}, "observations": []}
            doc.setdefault("pages", []).append(target)
        rows = target.setdefault("donnees", {}).setdefault(table, {})
        if not isinstance(rows, dict):
            raise ValueError("Structure de page inattendue")
        # Les autres pages qui portaient la même cellule sont alignées pour éviter une valeur fantôme à la fusion.
        for p in pages:
            other = (p.get("donnees") or {}).get(table) or {}
            if p is not target and isinstance(other.get(rid), dict) and col in other[rid]:
                other[rid][col] = value
        rows.setdefault(rid, {})[col] = value
        fid = f"{table}.{rid}.{col}"
        for holder in [target, doc]:
            obs = holder.get("observations")
            if not isinstance(obs, list):
                continue
            hit = [o for o in obs if isinstance(o, dict) and o.get("field_id") == fid]
            for o in hit:
                o["value"] = value
                o["corrige_manuellement"] = True
            if not hit and value is not None:
                obs.append({"field_id": fid, "table_id": table, "row_id": rid, "column_id": col, "value": value,
                            "unit": "DZD", "corrige_manuellement": True,
                            "source": {"page": target.get("numero_page_scannee")}})
    else:
        doc.setdefault(table, {}).setdefault(rid, {})[col] = value
    return doc


# ---------------------------------------------------------------------------
# Spécification transmise à la grille web (bilan_grid/index.html)
# ---------------------------------------------------------------------------
ALLOWED_COLS = {
    "ACTIF": {"montant_brut", "amortissements_provisions_pertes", "net_n", "net_n1"},
    "PASSIF": {"n", "n1"},
    "TCR": {"n_debit", "n_credit", "n1_debit", "n1_credit"},
}


def allowed_rows(table):
    if table == "ACTIF":
        return {rid for _, rid, _ in ACTIF_LAYOUT if not rid.startswith("_")}
    if table == "PASSIF":
        return {rid for _, rid, _ in PASSIF_LAYOUT if not rid.startswith("_")}
    return {rid for _, _, rid, _ in TCR_LAYOUT}


THRESHOLDS = {"min": ALERT_MIN_DZD, "medium": ALERT_MEDIUM_DZD, "high": ALERT_HIGH_DZD}


# ---------------------------------------------------------------------------
# Consolidation multi-exercices (plusieurs liasses d'un même client)
# Règle du notebook V29d (choose_candidates) : pour chaque (année, état), la colonne N
# de la liasse de l'année est prioritaire ; à défaut, la colonne N-1 de la liasse suivante.
# ---------------------------------------------------------------------------
GRID_COLS = {"ACTIF": ["brut", "amort", "net"], "PASSIF": ["v"], "TCR": ["debit", "credit"]}
FIELD_MAP = {
    "ACTIF": {"N": {"brut": "montant_brut", "amort": "amortissements_provisions_pertes", "net": "net_n"},
              "N1": {"net": "net_n1"}},
    "PASSIF": {"N": {"v": "n"}, "N1": {"v": "n1"}},
    "TCR": {"N": {"debit": "n_debit", "credit": "n_credit"}, "N1": {"debit": "n1_debit", "credit": "n1_credit"}},
}
MAX_YEARS = 5


def doc_label(doc, doc_id):
    return (doc.get("document") or {}).get("fichier_source") or doc_id


def consolidate(docs, year_overrides=None):
    """docs : {doc_id: json V29d}. Renvoie la grille multi-exercices et la traçabilité des sources."""
    year_overrides = year_overrides or {}
    years_of, idx_of, warnings = {}, {}, []
    for did, doc in sorted(docs.items()):
        y = year_overrides.get(did) or doc_year(doc)
        try:
            y = int(y) if y else None
        except (TypeError, ValueError):
            y = None
        years_of[did] = y
        idx_of[did] = index_doc(doc)[0]
        if not y:
            warnings.append(f"Exercice non détecté pour {doc_label(doc, did)} : à renseigner.")
    cands = {}
    for did, y in years_of.items():
        if not y:
            continue
        for table in ("ACTIF", "PASSIF", "TCR"):
            rows = idx_of[did].get(table) or {}
            if not rows:
                continue
            for period, yy, prio in (("N", y, 0), ("N1", y - 1, 1)):
                cols = set(FIELD_MAP[table][period].values())
                if any(any(c in vals for c in cols) for vals in rows.values()):
                    cands.setdefault((table, yy), []).append((prio, did, period))
    chosen = {}
    for key, lst in cands.items():
        lst.sort(key=lambda x: (x[0], x[1]))
        chosen[key] = lst[0]
        own = [x for x in lst if x[0] == 0]
        if len(own) > 1:
            warnings.append(f"{key[1]} {key[0]} : plusieurs liasses de la même année — "
                            f"{doc_label(docs[own[0][1]], own[0][1])} retenue.")
    years = sorted({y for (_, y) in chosen})[-MAX_YEARS:]
    data = {"ACTIF": {}, "PASSIF": {}, "TCR": {}}
    alt = {"ACTIF": {}, "PASSIF": {}, "TCR": {}}
    sources = {"ACTIF": {}, "PASSIF": {}, "TCR": {}}
    for (table, y), (prio, did, period) in chosen.items():
        if y not in years:
            continue
        for rid, vals in (idx_of[did].get(table) or {}).items():
            for c, jc in FIELD_MAP[table][period].items():
                if vals.get(jc) is not None:
                    data[table].setdefault(rid, {})[f"{y}:{c}"] = vals[jc]
        sources[table][str(y)] = {"doc": did, "period": period, "fichier": doc_label(docs[did], did),
                                  "pages": table_pages(docs[did], table), "annee_liasse": years_of[did]}
        # Contrôle inter-liasses : colonne N-1 de la liasse suivante vs colonne N retenue
        if period == "N":
            for prio2, did2, period2 in cands.get((table, y), []):
                if period2 != "N1":
                    continue
                for rid, vals in (idx_of[did2].get(table) or {}).items():
                    for c, jc in FIELD_MAP[table]["N1"].items():
                        if vals.get(jc) is not None:
                            alt[table].setdefault(rid, {})[f"{y}:{c}"] = {
                                "v": vals[jc], "src": f"{doc_label(docs[did2], did2)} (colonne N-1)"}
    return {"years": years, "data": data, "alt": alt, "sources": sources, "years_of": years_of,
            "warnings": warnings}


def map_grid_field(cons, table, colkey):
    """Clé de grille « 2024:brut » -> (doc_id, colonne JSON) ; ValueError si non modifiable."""
    try:
        y, c = colkey.split(":")
    except ValueError:
        raise ValueError(f"colonne inconnue : {colkey}")
    src = (cons["sources"].get(table) or {}).get(y)
    if not src:
        raise ValueError(f"aucune liasse source pour {table} {y}")
    jc = FIELD_MAP[table][src["period"]].get(c)
    if not jc:
        raise ValueError(f"{table} {y} : colonne {c} absente de la liasse source (colonne N-1)")
    return src["doc"], jc


def grid_spec():
    return {
        "ACTIF": {"layout": [list(x) for x in ACTIF_LAYOUT],
                  "formulas": {k: [list(p) for p in v] for k, v in ACTIF_FORMULAS.items()},
                  "cols": GRID_COLS["ACTIF"], "labels": {rid: lbl for lbl, rid, _ in ACTIF_LAYOUT}},
        "PASSIF": {"layout": [list(x) for x in PASSIF_LAYOUT],
                   "formulas": {k: [list(p) for p in v] for k, v in PASSIF_FORMULAS.items()},
                   "cols": GRID_COLS["PASSIF"], "labels": {rid: lbl for lbl, rid, _ in PASSIF_LAYOUT}},
        "TCR": {"layout": [list(x) for x in TCR_LAYOUT], "formulas": TCR_FORMULAS, "side": TCR_SIDE_RULES,
                "cols": GRID_COLS["TCR"], "labels": {rid: (d or c) for c, d, rid, _ in TCR_LAYOUT}},
    }


def _year_rows(cons, table, y):
    """Données d'un exercice remises au format « colonne N » pour réutiliser compute_balance/compute_tcr."""
    out = {}
    nmap = FIELD_MAP[table]["N"] if table != "ACTIF" else FIELD_MAP["ACTIF"]["N"]
    for rid, vals in cons["data"][table].items():
        for c, jc in nmap.items():
            v = vals.get(f"{y}:{c}")
            if v is not None:
                out.setdefault(rid, {})[jc] = v
    return out


def multi_controls(cons):
    """Mêmes contrôles que la grille web, côté serveur (pour la validation)."""
    alerts, cross, labels = [], [], {}
    for lbl, rid, _ in ACTIF_LAYOUT:
        labels[("ACTIF", rid)] = lbl
    for lbl, rid, _ in PASSIF_LAYOUT:
        labels[("PASSIF", rid)] = lbl
    for c, d, rid, _ in TCR_LAYOUT:
        labels[("TCR", rid)] = d or c
    for y in cons["years"]:
        ra, rp, rt = (_year_rows(cons, t, y) for t in ("ACTIF", "PASSIF", "TCR"))
        actif = compute_balance("ACTIF", ra, {})
        passif = compute_balance("PASSIF", rp, {})
        tcr = compute_tcr(rt, {})
        for table, cells, cols in (("ACTIF", actif, ("montant_brut", "amortissements_provisions_pertes", "net_n")),
                                   ("PASSIF", passif, ("n",))):
            for (rid, col), cell in cells.items():
                if col in cols and cell.level != "OK":
                    alerts.append({"annee": y, "etat": TABLE_LABELS[table], "rubrique": labels.get((table, rid), rid),
                                   "niveau": cell.level, "detail": cell.note})
        for (rid, period), cell in tcr.items():
            if period == "n" and cell.level != "OK":
                alerts.append({"annee": y, "etat": "TCR", "rubrique": labels.get(("TCR", rid), rid),
                               "niveau": cell.level, "detail": cell.note})
        a = actif[("total_general_actif", "net_n")].value
        p = passif[("total_general_passif", "n")].value
        if a is not None and p is not None:
            cross.append({"annee": y, "controle": "Total actif = Total passif", "ecart": a - p, "niveau": ecart_level(a - p)})
        r1 = tcr[("resultat_net_exercice", "n")].value
        r2 = passif[("resultat_net_passif", "n")].value
        if r1 is not None and r2 is not None:
            cross.append({"annee": y, "controle": "Résultat TCR = Résultat net au passif", "ecart": r1 - r2,
                          "niveau": ecart_level(r1 - r2)})
        # inter-liasses
        disp = {"ACTIF": actif, "PASSIF": passif}
        for table in ("ACTIF", "PASSIF", "TCR"):
            for rid, cols in cons["alt"][table].items():
                for ck, info in cols.items():
                    yy, c = ck.split(":")
                    if int(yy) != y:
                        continue
                    if table == "TCR":
                        cell = tcr.get((rid, "n"))
                        if cell is None:
                            continue
                        if cell.kind == "formula":
                            v = cell.value
                            mine = (-v if v is not None and v < 0 else None) if c == "debit" else (v if v is not None and v > 0 else None)
                        else:
                            mine = (rt.get(rid) or {}).get("n_" + c)
                    else:
                        jc = FIELD_MAP[table]["N"][c]
                        cell = disp[table].get((rid, jc))
                        mine = cell.value if cell else None
                    gap = (mine or 0.0) - (info["v"] or 0.0)
                    lv = ecart_level(gap)
                    if lv != "OK":
                        alerts.append({"annee": y, "etat": TABLE_LABELS[table], "rubrique": labels.get((table, rid), rid),
                                       "niveau": lv, "detail": f"Inter-liasses : {fmt_dzd(mine)} vs {fmt_dzd(info['v'])} DZD dans {info['src']}"})
    return {"alerts": alerts, "cross": cross}
