"""Comptes sociaux CNRC (Sidjilcom, format SCF) -> JSON V29d importable dans YaRisk.

Entrée : le texte copié depuis les trois onglets Actifs / Passifs / Comptes Résultats de Sidjilcom
(colonnes séparées par des tabulations, tableaux dans n'importe quel ordre).

    python tools/cnrc_import.py cnrc.txt --annee 2024 --raison "SPA EXEMPLE" --rc 23B0191279 [--nif ...] [-o sortie.json]

Le JSON produit se dépose dans YaRisk comme un JSON V29d (étape Dossier). Les montants sont en DZD.
Les rubriques agrégées du CNRC (CA, achats consommés, services extérieurs, dotations) sont placées sur une
rubrique de la liasse Série G et signalées « A VALIDER » dans le JSON (champ cnrc.a_valider).
"""
import argparse
import json
import re
import sys
from pathlib import Path

# (code CNRC, rubrique YaRisk, statut, remarque)
ACTIF_MAP = [
    ("2", None, "TITRE", "Titre de section (0 au CNRC)"),
    ("207", "ecarts_acquisition_goodwill", "OK", ""),
    ("20", "immobilisations_incorporelles", "OK", ""),
    ("21", "immobilisations_corporelles", "TOTAL", "Titre à 0 au CNRC : recalculé (terrains + bâtiments + autres + concession + en cours)"),
    ("211", "terrains", "OK", ""),
    ("2131", "batiments", "OK", ""),
    ("218", "autres_immobilisations_corporelles", "OK", ""),
    ("22", "immobilisations_en_concession", "OK", ""),
    ("23", "immobilisations_en_cours", "OK", ""),
    ("26+", "immobilisations_financieres", "TOTAL", "Titre à 0 au CNRC : recalculé"),
    ("265", "titres_mis_en_equivalence", "OK", ""),
    ("26", "autres_participations_creances", "OK", ""),
    ("271+", "autres_titres_immobilises", "OK", ""),
    ("274+", "prets_actifs_financiers_non_courants", "OK", ""),
    ("133", "impots_differes_actif", "OK", ""),
    ("188", None, "A VALIDER", "Comptes de liaison : absents de la liasse Série G — à reclasser par l'analyste si non nuls"),
    ("TNC", "total_actif_non_courant", "TOTAL", ""),
    ("3+", None, "TITRE", "Titre de section"),
    ("3", "stocks_encours", "OK", ""),
    ("4", "creances_emplois_assimiles", "TOTAL", "Titre à 0 au CNRC : recalculé"),
    ("41", "clients", "OK", ""),
    ("409+", "autres_debiteurs", "OK", ""),
    ("44+", "impots_assimiles_actif", "OK", ""),
    ("48", "autres_creances_assimiles", "OK", ""),
    ("5", "disponibilites_assimiles", "TOTAL", "Titre à 0 au CNRC : recalculé"),
    ("50-", "placements_financiers_courants", "OK", ""),
    ("51+", "tresorerie_actif", "OK", ""),
    ("TAC", "total_actif_courant", "TOTAL", ""),
    ("TGA", "total_general_actif", "TOTAL", ""),
]
PASSIF_MAP = [
    ("1", None, "TITRE", "Titre de section"),
    ("101", "capital_emis", "OK", ""),
    ("109", "capital_non_appele", "OK", ""),
    ("104+", "primes_reserves", "OK", ""),
    ("105", "ecart_reevaluation", "OK", ""),
    ("107", "ecart_equivalence", "OK", ""),
    ("12", "resultat_net_passif", "OK", ""),
    ("11", "report_a_nouveau", "OK", ""),
    ("PSC", "part_societe_consolidante", "OK", "Comptes consolidés uniquement"),
    ("PM", "part_minoritaires", "OK", "Comptes consolidés uniquement"),
    ("T1", "total_capitaux_propres", "TOTAL", ""),
    ("1+", None, "TITRE", "Titre de section"),
    ("16+", "emprunts_dettes_financieres", "OK", ""),
    ("134+", "impots_differes_provisionnes", "OK", ""),
    ("229", "autres_dettes_non_courantes", "OK", ""),
    ("15+", "provisions_produits_avance", "OK", ""),
    ("T2", "total_passifs_non_courants", "TOTAL", ""),
    ("4+", None, "TITRE", "Titre de section"),
    ("40", "fournisseurs_rattaches", "OK", ""),
    ("444+", "impots_passif", "OK", ""),
    ("42+", "autres_dettes", "OK", ""),
    ("52+", "tresorerie_passif", "OK", ""),
    ("T3", "total_passifs_courants", "TOTAL", ""),
    ("TGP", "total_general_passif", "TOTAL", ""),
]
# sens : P = produit (crédit si positif), C = charge (débit si positif), S = solde (crédit si positif, débit si négatif)
TCR_MAP = [
    ("70", "produits_fabriques", "P", "A VALIDER", "Chiffre d'affaires non ventilé au CNRC : placé en « Produits fabriqués » — à répartir (marchandises, prestations, travaux, annexes) si utile au V20"),
    ("72", "production_stockee_destockee", "S", "OK", ""),
    ("73", "production_immobilisee", "P", "OK", ""),
    ("74", "subvention_exploitation", "P", "OK", ""),
    ("T4", "production_exercice", "S", "TOTAL", ""),
    ("60", "matieres_premieres", "C", "A VALIDER", "Achats consommés non ventilés (marchandises, matières, approvisionnements, variation des stocks) : placés en « Matières premières »"),
    ("61/62", "autres_services", "C", "A VALIDER", "Services extérieurs non ventilés : placés en « Autres services » (locations, personnel extérieur et honoraires non isolés — impact CRF lignes 29 et 31)"),
    ("T5", "consommations_exercice", "C", "TOTAL", ""),
    ("T15", "valeur_ajoutee_exploitation", "S", "TOTAL", ""),
    ("63", "charges_personnel", "C", "OK", ""),
    ("64", "impots_taxes_assimiles", "C", "OK", ""),
    ("T6", "excedent_brut_exploitation", "S", "TOTAL", ""),
    ("75", "autres_produits_operationnels", "P", "OK", ""),
    ("65", "autres_charges_operationnelles", "C", "OK", ""),
    ("68", "dotations_amortissements", "C", "A VALIDER", "Dotations aux amortissements, provisions ET pertes de valeur regroupées : placées en « Dotations aux amortissements »"),
    ("78", "reprises_pertes_valeur_provisions", "P", "OK", ""),
    ("T7", "resultat_operationnel", "S", "TOTAL", ""),
    ("76", "produits_financiers", "P", "OK", ""),
    ("66", "charges_financieres", "C", "OK", ""),
    ("T8", "resultat_financier", "S", "TOTAL", ""),
    ("T9", "resultat_ordinaire", "S", "TOTAL", "Au CNRC : résultat ordinaire AVANT impôt ; dans la liasse Série G, les impôts viennent après"),
    ("695+", "impots_exigibles_resultats", "C", "OK", ""),
    ("692+", "impots_differes_resultats", "C", "OK", "Montant négatif = produit d'impôt différé"),
    ("T10", None, None, "CONTROLE", "Total des produits des activités ordinaires (pas dans la liasse) : sert au contrôle"),
    ("T11", None, None, "CONTROLE", "Total des charges des activités ordinaires (pas dans la liasse) : sert au contrôle"),
    ("T12", None, None, "CONTROLE", "Résultat net des activités ordinaires (pas dans la liasse) : sert au contrôle"),
    ("77", "elements_extraordinaires_produits", "P", "OK", ""),
    ("67", "elements_extraordinaires_charges", "C", "OK", ""),
    ("T13", "resultat_extraordinaire", "S", "TOTAL", ""),
    ("T14", "resultat_net_exercice", "S", "TOTAL", ""),
    ("T20", None, None, "CONSOLIDE", "Comptes consolidés uniquement"),
    ("T21", None, None, "CONSOLIDE", "Comptes consolidés uniquement"),
    ("DPM", None, None, "CONSOLIDE", "Comptes consolidés uniquement"),
    ("PG", None, None, "CONSOLIDE", "Comptes consolidés uniquement"),
]


def _num(s):
    s = str(s or "").strip().replace(" ", "").replace(" ", "")
    if s in ("", "-"):
        return None
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        raise ValueError(f"montant illisible : {s!r}")


def parse_tables(text):
    """Renvoie {'ACTIF': {code: [brut, amort, net, net_n1]}, 'PASSIF': {code: [n, n1]}, 'TCR': {code: [n, n1]}}."""
    out = {"ACTIF": {}, "PASSIF": {}, "TCR": {}}
    current = None
    for raw in text.replace(";", "\n").splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        cols = [c.strip() for c in line.split("\t")]
        head = " ".join(cols).lower()
        if head.startswith("numero comptes") or head.startswith("numéro comptes"):
            current = "ACTIF" if "montant brut" in head else ("PASSIF" if "designation_scf" in head else "TCR")
            continue
        if current is None or len(cols) < 3:
            continue
        code = cols[0]
        vals = [_num(c) for c in cols[2:]]
        out[current][code] = vals
    return out


def _put(rows, rid, col, v):
    if v is None or rid is None:
        return
    rows.setdefault(rid, {})[col] = round(v, 2)


def build_doc(tables, annee, raison=None, rc=None, nif=None):
    actif, passif, tcr, notes, missing = {}, {}, {}, [], []
    for code, rid, stt, rem in ACTIF_MAP:
        v = tables["ACTIF"].get(code)
        if v is None:
            missing.append(f"Actif {code}")
            continue
        if stt == "TITRE" or (stt == "TOTAL" and rid not in ("total_actif_non_courant", "total_actif_courant", "total_general_actif") and not any(v)):
            continue
        if rid is None:
            if any(x for x in v if x):
                notes.append({"table": "ACTIF", "code": code, "statut": stt, "remarque": rem, "valeurs": v})
            continue
        for col, x in zip(["montant_brut", "amortissements_provisions_pertes", "net_n", "net_n1"], v):
            if x or stt == "TOTAL":      # un 0 du CNRC = case vide de la liasse (sauf totaux)
                _put(actif, rid, col, x)
        if stt == "A VALIDER" and any(v):
            notes.append({"table": "ACTIF", "code": code, "rubrique": rid, "remarque": rem})
    for code, rid, stt, rem in PASSIF_MAP:
        v = tables["PASSIF"].get(code)
        if v is None:
            missing.append(f"Passif {code}")
            continue
        if stt == "TITRE" or rid is None:
            continue
        for col, x in zip(["n", "n1"], v):
            if x or stt == "TOTAL":
                _put(passif, rid, col, x)
    for code, rid, sens, stt, rem in TCR_MAP:
        v = tables["TCR"].get(code)
        if v is None:
            if stt not in ("CONSOLIDE", "CONTROLE"):
                missing.append(f"TCR {code}")
            continue
        if rid is None:
            continue
        for per, x in zip(("n", "n1"), v):
            if x is None:
                continue
            if sens == "P":
                side, val = ("credit", x) if x >= 0 else ("debit", -x)
            elif sens == "C":
                side, val = ("debit", x) if x >= 0 else ("credit", -x)
            else:
                side, val = ("credit", x) if x >= 0 else ("debit", -x)
            if val == 0 and stt != "TOTAL":
                continue
            _put(tcr, rid, f"{per}_{side}", val)
        if stt == "A VALIDER" and any(x for x in v if x):
            notes.append({"table": "TCR", "code": code, "rubrique": rid, "remarque": rem})
    # Chiffre d'affaires net (sous-total de la liasse, absent du CNRC) = 70
    ca = tables["TCR"].get("70")
    if ca:
        for per, x in zip(("n", "n1"), ca):
            if x is not None:
                _put(tcr, "chiffre_affaires_net", f"{per}_{'credit' if x >= 0 else 'debit'}", abs(x))
    # Contrôles propres au format CNRC
    ctrl = []
    t = tables["TCR"]
    def g(code, i):
        return (t.get(code) or [None, None])[i]
    for i, per in enumerate(("N", "N-1")):
        a, b = g("T10", i), g("T11", i)
        r, rn = g("T12", i), g("T14", i)
        if None not in (a, b, r):
            ctrl.append({"controle": "Produits − charges des activités ordinaires = résultat net ordinaire", "exercice": per,
                         "ecart": round(a - b - r, 2)})
        if None not in (r, rn):
            ctrl.append({"controle": "Résultat net ordinaire + extraordinaire = résultat net", "exercice": per,
                         "ecart": round(r + (g("T13", i) or 0) - rn, 2)})
    label = f"CNRC_{rc or 'RC'}_{annee}"
    page = lambda n, tpl, table, rows: {"page_id": f"cnrc_{table.lower()}", "numero_page_scannee": None,
                                        "classification": {"page_template": tpl, "types": [table], "page_utile": True,
                                                           "extraction_active": True, "route_source": "CNRC_SIDJILCOM"},
                                        "entete_page": {"entreprise": raison, "nif_15": nif}, "donnees": {table: rows}, "observations": []}
    return {
        "schema_version": "29.3",
        "document": {"fichier_source": label + ".json", "source": "CNRC — Sidjilcom (comptes sociaux déposés)", "rc": rc},
        "identite": {"entreprise": raison, "nif_15": nif, "rc": rc, "annee": int(annee)},
        "pages": [page(1, "ACTIF", "ACTIF", actif), page(2, "PASSIF", "PASSIF", passif), page(3, "TCR_FULL", "TCR", tcr)],
        "controles": {"cnrc": ctrl},
        "cnrc": {"a_valider": notes, "codes_absents": missing},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("fichier", help="texte copié depuis Sidjilcom (ou - pour l'entrée standard)")
    ap.add_argument("--annee", required=True, type=int, help="exercice (colonne « Exercice »)")
    ap.add_argument("--raison"); ap.add_argument("--rc"); ap.add_argument("--nif")
    ap.add_argument("-o", "--sortie")
    a = ap.parse_args(argv)
    text = sys.stdin.read() if a.fichier == "-" else Path(a.fichier).read_text(encoding="utf-8")
    doc = build_doc(parse_tables(text), a.annee, a.raison, a.rc, a.nif)
    out = Path(a.sortie or f"CNRC_{a.rc or 'RC'}_{a.annee}.json")
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{out} — à valider : {len(doc['cnrc']['a_valider'])} · codes absents : {len(doc['cnrc']['codes_absents'])}")


if __name__ == "__main__":
    main()
