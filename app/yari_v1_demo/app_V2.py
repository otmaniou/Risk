import copy
import hashlib
import html
import math
import json
from decimal import Decimal, InvalidOperation
import os
import re
import uuid
from datetime import datetime, timezone, date
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Ya-Risk | Démo V1", page_icon="📊", layout="wide")
st.title("Ya-Risk | Analyse financière")
st.caption("Pilote mono-opérateur · bilan ACTIF / PASSIF / TCR selon le modèle V20 · moteur V29d à connecter")

ROOT = Path(os.environ.get("YARISK_DATA_DIR", "./data")).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
PERSISTENT = bool(os.environ.get("YARISK_DATA_DIR"))
if not PERSISTENT:
    st.warning("Stockage local de démonstration : définissez YARISK_DATA_DIR vers un volume persistant approuvé avant d'utiliser des données réelles.")

FIELDS = [
    ("identifiant_national", "Identifiant National"),
    ("raison_sociale", "Raison sociale"),
    ("groupe_affaires", "Groupe d'affaires"),
    ("siege", "Siège"),
    ("racine_principale", "Racine principale"),
    ("secteur_activite", "Secteur d'activité"),
    ("sous_secteur_activite", "Sous-secteur d'activité"),
    ("segment", "Segment"),
    ("type_tiers", "Type tiers"),
    ("date_derniere_revue_annuelle", "Date de la dernière revue annuelle"),
    ("dernier_rating_valide", "Dernier rating validé"),
    ("societes_apparentees_engagements_bnpped", "Sociétés apparentées à engagements BNPPED"),
    ("maison_mere_cliente_bnpp_groupe", "Maison mère cliente de BNPP Groupe"),
    ("client_particularites_incidents", "Client avec particularités ou incidents"),
]
TRISTATE = {"societes_apparentees_engagements_bnpped", "maison_mere_cliente_bnpp_groupe", "client_particularites_incidents"}


SHEET_LAYOUT = {'ACTIF': [(9, None, 'ACTIFS NON COURANTS', 'section', False),
           (10,
            'ecarts_acquisition_goodwill',
            'Ecart d’acquisition – goodwill positif ou négatif',
            'detail',
            False),
           (11, 'immobilisations_incorporelles', 'Immobilisations incorporelles', 'detail', False),
           (12, 'immobilisations_corporelles', 'Immobilisations corporelles', 'group', False),
           (13, 'terrains', 'Terrains', 'detail', False),
           (14, 'batiments', 'Bâtiments', 'detail', False),
           (15, 'autres_immobilisations_corporelles', 'Autres immobilisations corporelles', 'detail', False),
           (16, 'immobilisations_en_concession', 'Immobilisations en concession', 'detail', False),
           (17, 'immobilisations_en_cours', 'Immobilisations en cours', 'detail', False),
           (18, 'immobilisations_financieres', 'Immobilisations financières', 'group', False),
           (19, 'titres_mis_en_equivalence', 'Titres mis en équivalence', 'detail', False),
           (20,
            'autres_participations_creances',
            'Autres participations et créances rattachées',
            'detail',
            False),
           (21, 'autres_titres_immobilises', 'Autres titres immobilisés', 'detail', False),
           (22,
            'prets_actifs_financiers_non_courants',
            'Prêts et autres actifs financiers non courants',
            'detail',
            False),
           (23, 'impots_differes_actif', 'Impôts différés actif', 'detail', False),
           (24, 'total_actif_non_courant', 'TOTAL ACTIF NON COURANT', 'total', False),
           (25, None, 'ACTIFS COURANTS', 'section', False),
           (26, 'stocks_encours', 'Stocks et encours', 'detail', False),
           (27, 'creances_emplois_assimiles', 'Créances et emplois assimilés', 'group', False),
           (28, 'clients', 'Clients', 'detail', False),
           (29, 'autres_debiteurs', 'Autres débiteurs', 'detail', False),
           (30, 'impots_assimiles_actif', 'Impôts et assimilés', 'detail', False),
           (31, 'autres_creances_assimiles', 'Autres créances et emplois assimilés', 'detail', False),
           (32, 'disponibilites_assimiles', 'Disponibilités et assimilés', 'group', False),
           (33,
            'placements_financiers_courants',
            'Placements et autres actifs financiers courants',
            'detail',
            False),
           (34, 'tresorerie_actif', 'Trésorerie', 'detail', False),
           (35, 'total_actif_courant', 'TOTAL ACTIF COURANT', 'total', False),
           (36, 'total_general_actif', 'TOTAL GENERAL ACTIF', 'total', False)],
 'PASSIF': [(5, None, 'CAPITAUX PROPRES :', 'section', False),
            (6, 'capital_emis', 'Capital émis', 'detail', False),
            (7, 'capital_non_appele', 'Capital non appelé', 'detail', False),
            (8, 'primes_reserves', 'Primes et réserves- Réserves consolidées(1)', 'detail', False),
            (9, 'ecart_reevaluation', 'Ecarts de réévaluation', 'detail', False),
            (10, 'ecart_equivalence', 'Ecart d’équivalence (1)', 'detail', False),
            (11, 'resultat_net_passif', 'Résultat net - Résultat net part du groupe (1)', 'detail', False),
            (12, 'report_a_nouveau', 'Autres capitaux propres – Report à nouveau', 'detail', False),
            (13, 'part_societe_consolidante', 'Part de la société consolidante (1)', 'detail', False),
            (14, 'part_minoritaires', 'Part des minoritaires (1)', 'detail', False),
            (15, 'total_capitaux_propres', 'TOTAL I (KDZD)', 'total', False),
            (16, None, 'PASSIFS NON-COURANTS :', 'section', False),
            (17, 'emprunts_dettes_financieres', 'Emprunts et dettes financières', 'detail', False),
            (18, 'impots_differes_provisionnes', 'Impôts (différés et provisionnés)', 'detail', False),
            (19, 'autres_dettes_non_courantes', 'Autres dettes non courantes', 'detail', False),
            (20, 'provisions_produits_avance', 'Provisions et produits constatés d’avance', 'detail', False),
            (21, 'total_passifs_non_courants', 'TOTAL II (KDZD)', 'total', False),
            (22, None, 'PASSIFS COURANTS :', 'section', False),
            (23, 'fournisseurs_rattaches', 'Fournisseurs et comptes rattachés', 'detail', False),
            (24, 'impots_passif', 'Impôts', 'detail', False),
            (25, 'autres_dettes', 'Autres dettes', 'group', False),
            (26, 'tresorerie_passif', 'Trésorerie Passif', 'detail', False),
            (27, 'total_passifs_courants', 'TOTAL III (KDZD)', 'total', False),
            (28, 'total_general_passif', 'TOTAL PASSIF (I+II+III) (KDZD)', 'total', False)],
 'TCR': [(6, 'ventes_marchandises', 'Ventes de marchandises', 'detail', False),
         (7, 'produits_fabriques', 'Production \nvendue — Produits fabriqués', 'detail', False),
         (8, 'prestations_services', 'Prestations de services', 'detail', True),
         (9, 'ventes_travaux', 'Vente de travaux', 'detail', True),
         (10, 'produits_annexes', 'Produits annexes', 'detail', False),
         (11, 'rabais_remises_ristournes_accordes', 'Rabais, remises, ristournes accordés', 'detail', False),
         (12,
          'chiffre_affaires_net',
          'Chiffre d’affaires net des Rabais, remises, ristournes',
          'group',
          False),
         (13, 'production_stockee_destockee', 'Production stockée ou déstockée', 'detail', False),
         (14, 'production_immobilisee', 'Production immobilisée', 'detail', False),
         (15, 'subvention_exploitation', 'Subventions d’exploitation', 'detail', False),
         (16, 'production_exercice', 'I-Production de l’exercice', 'section', False),
         (17, 'achats_marchandises_vendues', 'Achats de marchandises vendues', 'detail', False),
         (18, 'matieres_premieres', 'Matières premières', 'detail', False),
         (19, 'autres_approvisionnements', 'Autres approvisionnements', 'detail', False),
         (20, 'variation_stocks', 'Variations des stocks', 'detail', False),
         (21, 'achats_etudes_prestations', 'Achats d’études et de prestations de services', 'detail', False),
         (22, 'autres_consommations', 'Autres consommations', 'detail', False),
         (23,
          'rabais_remises_ristournes_obtenus_achats',
          'Rabais, remises, ristournes obtenus sur achats',
          'detail',
          False),
         (24, 'sous_traitance_generale', 'Services \nextérieurs — Sous-traitance générale', 'detail', False),
         (25, 'locations', 'Locations', 'detail', True),
         (26, 'entretien_reparations', 'Entretien, réparations et maintenance', 'detail', True),
         (27, 'primes_assurances', "Primes d'assurances", 'detail', True),
         (28, 'personnel_exterieur', 'Personnel extérieur à l’entreprise', 'detail', True),
         (29, 'remuneration_intermediaires', 'Rémunération d’intermédiaires et honoraires', 'detail', True),
         (30, 'publicite', 'Publicité', 'detail', True),
         (31, 'deplacements_missions', 'Déplacements, missions et réceptions', 'detail', True),
         (32, 'autres_services', 'Autres services', 'detail', False),
         (33,
          'rabais_remises_ristournes_obtenus_services',
          'Rabais, remises, ristournes obtenus sur services extérieurs',
          'detail',
          False),
         (34, 'consommations_exercice', 'II-Consommations de l’exercice', 'section', False),
         (35, 'valeur_ajoutee_exploitation', 'III-Valeur ajoutée d’exploitation (I–II)', 'section', False),
         (36, 'charges_personnel', 'Charges de personnel', 'detail', True),
         (37, 'impots_taxes_assimiles', 'Impôts et taxes et versements assimilés ', 'detail', True),
         (38, 'excedent_brut_exploitation', 'IV-Excédent brut d’exploitation', 'section', False),
         (39, 'autres_produits_operationnels', 'Autres produits opérationnels', 'detail', False),
         (40, 'autres_charges_operationnelles', 'Autres charges opérationnelles', 'detail', False),
         (41, 'dotations_amortissements', 'Dotations aux amortissements', 'detail', False),
         (42, 'provisions', 'Provision', 'detail', False),
         (43, 'pertes_valeur', 'Pertes de valeur', 'detail', False),
         (44,
          'reprises_pertes_valeur_provisions',
          'Reprise sur pertes de valeur et provisions ',
          'detail',
          False),
         (45, 'resultat_operationnel', 'V-Résultat opérationnel', 'section', False),
         (46, 'produits_financiers', 'Produits financiers', 'detail', False),
         (47, 'charges_financieres', 'Charges financières', 'detail', False),
         (48, 'resultat_financier', 'VI-Résultat financier', 'section', False),
         (49, 'resultat_ordinaire', 'VII-Résultat ordinaire (V+VI)', 'section', False),
         (50,
          'elements_extraordinaires_produits',
          'Eléments extraordinaires (produits) (*)',
          'detail',
          False),
         (51, 'elements_extraordinaires_charges', 'Eléments extraordinaires (Charges) (*)', 'detail', False),
         (52, 'resultat_extraordinaire', 'VIII-Résultat extraordinaire', 'section', False),
         (53, 'impots_exigibles_resultats', 'Impôts exigibles sur résultats', 'detail', False),
         (54, 'impots_differes_resultats', 'Impôts différés (variations) sur résultats', 'detail', False),
         (55, 'resultat_net_exercice', 'IX - RESULTAT NET DE L’EXERCICE', 'total', False)]}

FORMULA_COLUMNS = {'ACTIF': {'ecarts_acquisition_goodwill': ['net_n', 'net_n1'],
           'immobilisations_incorporelles': ['net_n', 'net_n1'],
           'immobilisations_corporelles': ['montant_brut', 'amortissements_provisions_pertes', 'net_n', 'net_n1'],
           'terrains': ['net_n', 'net_n1'],
           'batiments': ['net_n', 'net_n1'],
           'autres_immobilisations_corporelles': ['net_n', 'net_n1'],
           'immobilisations_en_concession': ['net_n', 'net_n1'],
           'immobilisations_en_cours': ['net_n', 'net_n1'],
           'immobilisations_financieres': ['montant_brut', 'amortissements_provisions_pertes', 'net_n', 'net_n1'],
           'titres_mis_en_equivalence': ['net_n', 'net_n1'],
           'autres_participations_creances': ['net_n', 'net_n1'],
           'autres_titres_immobilises': ['net_n', 'net_n1'],
           'prets_actifs_financiers_non_courants': ['net_n', 'net_n1'],
           'impots_differes_actif': ['net_n', 'net_n1'],
           'total_actif_non_courant': ['montant_brut', 'amortissements_provisions_pertes', 'net_n', 'net_n1'],
           'stocks_encours': ['net_n', 'net_n1'],
           'creances_emplois_assimiles': ['montant_brut', 'amortissements_provisions_pertes', 'net_n', 'net_n1'],
           'clients': ['net_n', 'net_n1'],
           'autres_debiteurs': ['net_n', 'net_n1'],
           'impots_assimiles_actif': ['net_n', 'net_n1'],
           'autres_creances_assimiles': ['net_n', 'net_n1'],
           'disponibilites_assimiles': ['montant_brut', 'amortissements_provisions_pertes', 'net_n', 'net_n1'],
           'placements_financiers_courants': ['net_n', 'net_n1'],
           'tresorerie_actif': ['net_n', 'net_n1'],
           'total_actif_courant': ['montant_brut', 'amortissements_provisions_pertes', 'net_n', 'net_n1'],
           'total_general_actif': ['montant_brut', 'amortissements_provisions_pertes', 'net_n', 'net_n1']},
 'PASSIF': {'capital_emis': [],
            'capital_non_appele': [],
            'primes_reserves': [],
            'ecart_reevaluation': [],
            'ecart_equivalence': [],
            'resultat_net_passif': [],
            'report_a_nouveau': [],
            'part_societe_consolidante': [],
            'part_minoritaires': [],
            'total_capitaux_propres': ['n', 'n1'],
            'emprunts_dettes_financieres': [],
            'impots_differes_provisionnes': [],
            'autres_dettes_non_courantes': [],
            'provisions_produits_avance': [],
            'total_passifs_non_courants': ['n', 'n1'],
            'fournisseurs_rattaches': [],
            'impots_passif': [],
            'autres_dettes': ['n', 'n1'],
            'tresorerie_passif': [],
            'total_passifs_courants': ['n', 'n1'],
            'total_general_passif': ['n', 'n1']},
 'TCR': {'ventes_marchandises': [],
         'produits_fabriques': [],
         'prestations_services': [],
         'ventes_travaux': [],
         'produits_annexes': [],
         'rabais_remises_ristournes_accordes': [],
         'chiffre_affaires_net': ['n_debit', 'n_credit', 'n1_debit', 'n1_credit'],
         'production_stockee_destockee': [],
         'production_immobilisee': [],
         'subvention_exploitation': [],
         'production_exercice': ['n_debit', 'n_credit', 'n1_debit', 'n1_credit'],
         'achats_marchandises_vendues': [],
         'matieres_premieres': [],
         'autres_approvisionnements': [],
         'variation_stocks': [],
         'achats_etudes_prestations': [],
         'autres_consommations': [],
         'rabais_remises_ristournes_obtenus_achats': [],
         'sous_traitance_generale': [],
         'locations': [],
         'entretien_reparations': [],
         'primes_assurances': [],
         'personnel_exterieur': [],
         'remuneration_intermediaires': [],
         'publicite': [],
         'deplacements_missions': [],
         'autres_services': [],
         'rabais_remises_ristournes_obtenus_services': [],
         'consommations_exercice': ['n_debit', 'n_credit', 'n1_debit', 'n1_credit'],
         'valeur_ajoutee_exploitation': ['n_debit', 'n_credit', 'n1_debit', 'n1_credit'],
         'charges_personnel': [],
         'impots_taxes_assimiles': [],
         'excedent_brut_exploitation': ['n_debit', 'n_credit', 'n1_debit', 'n1_credit'],
         'autres_produits_operationnels': [],
         'autres_charges_operationnelles': [],
         'dotations_amortissements': [],
         'provisions': [],
         'pertes_valeur': [],
         'reprises_pertes_valeur_provisions': [],
         'resultat_operationnel': ['n_debit', 'n_credit', 'n1_debit', 'n1_credit'],
         'produits_financiers': [],
         'charges_financieres': [],
         'resultat_financier': ['n_debit', 'n_credit', 'n1_debit', 'n1_credit'],
         'resultat_ordinaire': ['n_debit', 'n_credit', 'n1_debit', 'n1_credit'],
         'elements_extraordinaires_produits': [],
         'elements_extraordinaires_charges': [],
         'resultat_extraordinaire': ['n_debit', 'n_credit', 'n1_debit', 'n1_credit'],
         'impots_exigibles_resultats': [],
         'impots_differes_resultats': [],
         'resultat_net_exercice': ['n_debit', 'n_credit', 'n1_debit', 'n1_credit']}}

def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def safe_id(value):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)[:90] or "inconnu"


def dossier_path(d):
    return ROOT / "dossiers" / safe_id(d["client"]["identifiant_national"]) / d["execution_id"]


def flatten(node, prefix=""):
    result = []
    if isinstance(node, dict):
        for key, val in node.items():
            result.extend(flatten(val, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(node, list):
        for i, val in enumerate(node):
            result.extend(flatten(val, f"{prefix}[{i}]"))
    elif isinstance(node, (int, float, str)) and not isinstance(node, bool):
        result.append({"Champ": prefix, "Valeur": node})
    return result


def assign_path(obj, path, value):
    # Editing is limited to already-existing scalar leaf paths.
    parts = re.findall(r"([^\.\[\]]+)|\[(\d+)\]", path)
    keys = [int(b) if b else a for a, b in parts]
    cur = obj
    for key in keys[:-1]:
        cur = cur[key]
    old = cur[keys[-1]]
    if isinstance(old, bool) or not (old is None or isinstance(old, (str, int, float))):
        raise ValueError("Champ non modifiable")
    if old is None and not _scalar_number(value):
        raise ValueError("Une cellule vide ne peut recevoir qu’un montant numérique")
    if isinstance(old, int):
        value = int(value) if int(value) == value else float(value)
    elif isinstance(old, float):
        value = float(value)
    cur[keys[-1]] = value


# Les lignes/sections et le statut des cellules à formule proviennent du modèle Excel V20.
SHEET_COLUMNS = {
    "ACTIF": [
        ("Net", "net_n1", "N-1"),
        ("Brut", "montant_brut", "N"),
        ("Amort. / provisions", "amortissements_provisions_pertes", "N"),
        ("Net", "net_n", "N"),
    ],
    "PASSIF": [("Montant", "n1", "N-1"), ("Montant", "n", "N")],
    "TCR": [
        ("Débit", "n1_debit", "N-1"), ("Crédit", "n1_credit", "N-1"),
        ("Débit", "n_debit", "N"), ("Crédit", "n_credit", "N"),
    ],
}


FINANCIAL_CSS = """
<style>
.yr-wrap {border: 1px solid #C6E5D4; border-radius: 9px; overflow:auto;
          max-height:670px; background:#fff; box-shadow:0 1px 5px #173D2C0B;}
.yr-sheet {border-collapse:separate; border-spacing:0; min-width:770px;
           width:100%; font-family:Arial,Helvetica,sans-serif; font-size:12.5px; color:#1E2B26;}
.yr-sheet th,.yr-sheet td {padding:8px 11px; border-right:1px solid #DCEAE2;
                          border-bottom:1px solid #E6EFE8; line-height:1.28;}
.yr-sheet .yr-top {background:#00915A; color:#fff; font-weight:700; text-align:center;
                   position:sticky; top:0; z-index:4; height:36px;}
.yr-sheet .yr-second {background:#00573F; color:#fff; font-weight:600; text-align:center;
                      position:sticky; top:36px; z-index:4; height:36px;}
.yr-sheet .yr-label {min-width:310px; width:38%; text-align:left; position:sticky; left:0;
                     z-index:2; box-shadow:2px 0 2px #0F3A2413;}
.yr-sheet .yr-top.yr-label {z-index:6;}
.yr-sheet .yr-second.yr-label {z-index:6;}
.yr-sheet .yr-val {min-width:125px; text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap;}
.yr-sheet .yr-body td.yr-label {background:#fff;}
.yr-sheet .yr-body td.yr-input {background:#FFF8E1; color:#1F4E9A;}
.yr-sheet .yr-body td.yr-formula {background:#fff; color:#1E2B26;}
.yr-sheet .yr-group td, .yr-sheet .yr-group td.yr-label {background:#EAF5EF; color:#00573F; font-weight:700;}
.yr-sheet .yr-section td,.yr-sheet .yr-section td.yr-label {background:#C6E5D4; color:#00573F; font-weight:700;}
.yr-sheet .yr-total td,.yr-sheet .yr-total td.yr-label {background:#00573F; color:#fff; font-weight:700;}
.yr-sheet tr .yr-changed {box-shadow: inset 0 0 0 2px #B98212;}
.yr-sheet .yr-empty {opacity:.6;}
.yr-sheet .yr-fn {font-size:9px; vertical-align:super; color:#32715A; margin-left:2px;}
.yr-sheet .yr-total .yr-fn {color:#DBF7E6;}
.yr-sheet .yr-indent {padding-left:24px;}
.yr-legend {display:flex; flex-wrap:wrap; gap:13px; align-items:center; font-size:12px; margin:10px 0 14px; color:#425C51;}
.yr-dot {display:inline-block; width:11px; height:11px; border:1px solid #d0dfd7;
         border-radius:2px; margin-right:5px; vertical-align:-1px;}
</style>
"""


def _scalar_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _collect_financial_data(financial):
    """Associe chaque valeur du document V29d à son chemin JSON modifiable.

    Le premier champ non nul rencontré par page est conservé. Des lectures
    concurrentes différentes sont signalées plutôt que fusionnées en silence.
    """
    found = {key: {} for key in SHEET_COLUMNS}
    conflicts = []

    def insert(table, row, col, value, path, page=None):
        if table not in SHEET_COLUMNS or not isinstance(row, str) or not isinstance(col, str):
            return
        known = {key for _label, key, _period in SHEET_COLUMNS[table]}
        allowed_rows = {r[1] for r in SHEET_LAYOUT[table] if r[1]}
        if col not in known or row not in allowed_rows:
            return
        if value is not None and not _scalar_number(value):
            return
        record = {"value": value, "path": path, "page": page}
        old = found[table].setdefault(row, {}).get(col)
        if old is None or (old["value"] is None and value is not None):
            found[table][row][col] = record
        elif old["value"] is not None and value is not None and old["value"] != value:
            conflicts.append({"table": table, "row": row, "column": col,
                              "first": old["value"], "other": value,
                              "first_page": old["page"], "other_page": page})

    if not isinstance(financial, dict):
        return found, conflicts

    # Contrat d'origine du notebook V29d : pages[i].donnees[ACTIF|PASSIF|TCR].
    pages = financial.get("pages")
    if isinstance(pages, list):
        for i, p in enumerate(pages):
            if not isinstance(p, dict):
                continue
            group = p.get("donnees") or {}
            if not isinstance(group, dict):
                continue
            for table in SHEET_COLUMNS:
                rows = group.get(table)
                if not isinstance(rows, dict):
                    continue
                for row, columns in rows.items():
                    if not isinstance(columns, dict):
                        continue
                    for col, value in columns.items():
                        insert(table, row, col, value,
                               f"pages[{i}].donnees.{table}.{row}.{col}",
                               p.get("numero_page_scannee", i + 1))

    # Compatibilité avec un JSON déjà regroupé par tableau, sans pages.
    for prefix, group in (("", financial), ("donnees", financial.get("donnees")),
                          ("tables", financial.get("tables"))):
        if not isinstance(group, dict):
            continue
        for table in SHEET_COLUMNS:
            rows = group.get(table)
            if not isinstance(rows, dict):
                continue
            for row, columns in rows.items():
                if not isinstance(columns, dict):
                    continue
                for col, value in columns.items():
                    path = f"{prefix + '.' if prefix else ''}{table}.{row}.{col}"
                    insert(table, row, col, value, path)

    # Observation par field_id : solution de repli si les pages n'existent pas.
    if not any(found[k] for k in found) and isinstance(financial.get("observations"), list):
        for i, ob in enumerate(financial["observations"]):
            if not isinstance(ob, dict):
                continue
            field_id = ob.get("field_id")
            parts = field_id.split(".") if isinstance(field_id, str) else []
            if len(parts) == 3 and "value" in ob:
                source = ob.get("source") or {}
                page = source.get("page") if isinstance(source, dict) else None
                insert(parts[0], parts[1], parts[2], ob["value"],
                       f"observations[{i}].value", page)
    return found, conflicts


def _display_amount(value, unit, decimals):
    if value is None:
        return "—"
    number = value / 1000 if unit == "KDZD" else value
    text = f"{number:,.{decimals}f}"
    return text.replace(",", "\u202f").replace(".", ",")


def _parse_dzd_amount(s):
    s = s.strip().replace("\u202f", "").replace("\xa0", "").replace(" ", "")
    if not s:
        raise ValueError("Saisissez un montant en DZD.")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        amount = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError("Montant non numérique. Exemple : 1 250 000,50") from exc
    if not amount.is_finite():
        raise ValueError("Le montant doit être fini.")
    if abs(amount) > Decimal("1e18"):
        raise ValueError("Montant hors limite autorisée pour cette démo.")
    return int(amount) if amount == amount.to_integral_value() else float(amount)


def _render_financial_grid(table, records, corrections, unit="KDZD", decimals=2):
    cols = SHEET_COLUMNS[table]
    by_period = []
    for _label, _field, year in cols:
        if not by_period or by_period[-1][0] != year:
            by_period.append((year, 1))
        else:
            by_period[-1] = (year, by_period[-1][1] + 1)
    parts = [FINANCIAL_CSS, '<div class="yr-wrap"><table class="yr-sheet">', '<thead><tr>',
             '<th class="yr-top yr-label" rowspan="2">Rubriques / postes financiers</th>']
    for period, span in by_period:
        parts.append(f'<th class="yr-top" colspan="{span}">Exercice {html.escape(period)}</th>')
    parts.append('</tr><tr>')
    for label, _field, _period in cols:
        parts.append(f'<th class="yr-second">{html.escape(label)} ({html.escape(unit)})</th>')
    parts.append('</tr></thead><tbody>')
    for number, row_id, label, kind, indented in SHEET_LAYOUT[table]:
        name = html.escape(label)
        pad = ' yr-indent' if indented else ''
        parts.append(f'<tr class="yr-{kind}"><td class="yr-label{pad}" title="Ligne Excel {number}">{name}</td>')
        for _title, field, _year in cols:
            item = records.get(row_id, {}).get(field) if row_id else None
            value = item["value"] if item else None
            formula = bool(row_id and field in FORMULA_COLUMNS[table].get(row_id, []))
            cell_style = 'yr-formula' if formula else 'yr-input'
            changed = ' yr-changed' if item and item["path"] in corrections else ''
            empty = ' yr-empty' if value is None else ''
            hint = ('Formule dans le modèle V20 ; montant extrait du PDF, non recalculé ici. '
                    if formula else 'Champ de saisie du modèle V20. ')
            if item and item.get("page"):
                hint += f'Page PDF : {item["page"]}. '
            if item and item["path"] in corrections:
                hint += 'Valeur corrigée et historisée.'
            amount = _display_amount(value, unit, decimals)
            suffix = '<span class="yr-fn">ƒ</span>' if formula and value is not None else ''
            parts.append(f'<td class="yr-val {cell_style}{changed}{empty}" '
                         f'title="{html.escape(hint, quote=True)}">{amount}{suffix}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div>')
    return ''.join(parts)


def _financial_edit_form(table, records, data, dossier):
    # Les cellules à formule du classeur V20 ne sont jamais proposées en saisie.
    eligible = []
    lookup = {r[1]: r[2] for r in SHEET_LAYOUT[table] if r[1]}
    for row_id, columns in records.items():
        editable = {field: item for field, item in columns.items()
                    if item.get("path") and field not in FORMULA_COLUMNS[table].get(row_id, [])}
        if editable:
            eligible.append((row_id, editable))
    if not eligible:
        st.caption("Aucun champ de saisie exploitable trouvé pour cette feuille.")
        return
    eligible.sort(key=lambda x: next((i for i, r in enumerate(SHEET_LAYOUT[table]) if r[1] == x[0]), 999))
    with st.expander(f"Corriger un montant — {table}", expanded=False):
        st.caption("Saisie en DZD (valeur source), justification obligatoire. Les cellules portant une formule V20 ne sont pas éditables.")
        row_ids = [row_id for row_id, _columns in eligible]
        row_id = st.selectbox("Rubrique", row_ids, format_func=lambda k: lookup.get(k, k), key=f"financial_row_{table}")
        editable = dict(eligible)[row_id]
        col_id = st.selectbox("Colonne", list(editable),
                              format_func=lambda c: next((f"{period} · {label}" for label, key, period in SHEET_COLUMNS[table] if key == c), c),
                              key=f"financial_col_{table}_{row_id}")
        item = editable[col_id]
        old = item["value"]
        with st.form(f"fin_edit_{table}_{row_id}_{col_id}"):
            new_value = st.text_input("Montant corrigé (DZD)", value="" if old is None else str(old))
            justification = st.text_area("Motif de correction", max_chars=1000)
            submitted = st.form_submit_button("Enregistrer la correction")
        if submitted:
            if not justification.strip():
                st.error("Le motif de correction est obligatoire.")
                return
            try:
                numeric = _parse_dzd_amount(new_value)
                if numeric == old:
                    st.info("Aucune modification du montant.")
                    return
                changed = copy.deepcopy(data)
                assign_path(changed, item["path"], numeric)
                path = dossier_path(dossier)
                log_path = path / "corrections.json"
                logs = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
                logs.append({"date": now(), "table": table, "rubrique": row_id, "colonne": col_id,
                             "champ": item["path"], "avant": old, "apres": numeric,
                             "motif": justification.strip(), "unite": "DZD"})
                atomic_json(log_path, logs)
                atomic_json(path / "extraction_corrigee.json", changed)
                st.session_state.edited = changed
                st.session_state.dossier["validation"] = {"statut": "non_valide"}
                atomic_json(path / "dossier.json", st.session_state.dossier)
                st.success("Montant corrigé et historisé. Vérification métier toujours requise.")
                st.rerun()
            except (KeyError, IndexError, ValueError, TypeError, OSError) as exc:
                st.error(f"Impossible d'enregistrer cette correction : {exc}")


if "dossier" not in st.session_state:
    st.session_state.dossier = None
if "edited" not in st.session_state:
    st.session_state.edited = None

client_tab, import_tab, results_tab, validation_tab, archive_tab = st.tabs([
    "1 · Fiche client", "2 · Import", "3 · Bilan", "4 · Validation", "5 · Archive"
])

with client_tab:
    st.subheader("Identification et profil client")
    st.info("L'identifiant national et la raison sociale sont obligatoires pour préparer un dossier.")
    with st.form("client_form"):
        cols = st.columns(2)
        for i, (key, label) in enumerate(FIELDS):
            with cols[i % 2]:
                if key in TRISTATE:
                    st.selectbox(label, ["Non renseigné", "Oui", "Non"], key=f"field_{key}")
                elif key == "date_derniere_revue_annuelle":
                    st.text_input(label + " (AAAA-MM-JJ)", key=f"field_{key}")
                else:
                    st.text_input(label, key=f"field_{key}")
        st.text_area("Précisions sur les particularités ou incidents", key="field_observations")
        submitted = st.form_submit_button("Enregistrer la fiche dans la session")
    if submitted:
        st.success("Fiche prête. Passez à l'onglet Import.")

with import_tab:
    st.subheader("Préparation du dossier")
    fiscal_year = st.number_input("Exercice fiscal", min_value=1990, max_value=2100, value=2025, step=1)
    pdf = st.file_uploader("Liasse fiscale PDF", type=["pdf"], key="pdf")
    json_file = st.file_uploader("JSON financier existant (optionnel, pour la démonstration)", type=["json"], key="json")
    if st.button("Créer le dossier", type="primary"):
        client = {key: st.session_state.get(f"field_{key}", "") for key, _ in FIELDS}
        client["observations"] = st.session_state.get("field_observations", "")
        if not client["identifiant_national"].strip() or not client["raison_sociale"].strip():
            st.error("Identifiant National et Raison sociale obligatoires.")
        elif pdf is None:
            st.error("Importer une liasse PDF.")
        elif not pdf.getvalue().startswith(b"%PDF-"):
            st.error("Signature PDF non reconnue.")
        else:
            financial = None
            if json_file is not None:
                try:
                    financial = json.loads(json_file.getvalue())
                    if not isinstance(financial, dict):
                        raise ValueError("Le JSON racine doit être un objet.")
                except (ValueError, UnicodeDecodeError) as exc:
                    st.error(f"JSON invalide : {exc}")
                    st.stop()
            run = uuid.uuid4().hex
            dossier = {
                "schema_version": "yarisk-demo-v1", "execution_id": run, "created_at": now(),
                "client": client, "exercice": int(fiscal_year),
                "document": {"nom_original": pdf.name, "sha256": hashlib.sha256(pdf.getvalue()).hexdigest()},
                "extraction": {"statut": "json_importe_non_verifie" if financial is not None else "moteur_non_connecte", "source": json_file.name if json_file else None},
                "validation": {"statut": "non_valide"}
            }
            path = dossier_path(dossier)
            path.mkdir(parents=True, exist_ok=False)
            (path / "source.pdf").write_bytes(pdf.getvalue())
            atomic_json(path / "dossier.json", dossier)
            if financial is not None:
                atomic_json(path / "extraction_originale.json", financial)
            st.session_state.dossier = dossier
            st.session_state.edited = financial
            st.success(f"Dossier créé : {run}")
            if financial is None:
                st.warning("Aucune extraction exécutée. Importez un JSON V29d pour afficher les données.")

with results_tab:
    st.subheader("Bilan financier — revue avant validation")
    dossier = st.session_state.dossier
    data = st.session_state.edited
    if dossier is None or data is None:
        st.info("Aperçu du modèle V20 sans données. Pour renseigner les montants, préparez un dossier avec PDF et JSON V29d dans les deux premiers onglets.")
        for table, preview_tab in zip(SHEET_COLUMNS, st.tabs(["ACTIF", "PASSIF", "TCR"])):
            with preview_tab:
                st.markdown(_render_financial_grid(table, {}, set(), "KDZD", 2), unsafe_allow_html=True)
        st.caption("Grilles structurelles uniquement : aucun montant fictif ou extraction IA n'a été généré.")
    else:
        records, conflicts = _collect_financial_data(data)
        st.caption(f"{dossier['client'].get('raison_sociale', 'Client')} · "
                   f"Exercice N : {dossier.get('exercice', '—')} · "
                   "Source : JSON importé (non vérifié) · Référentiel : Excel Analyste V20")
        st.warning("Montants extraits du PDF, sans certification. Les cellules marquées ƒ correspondent "
                   "à des formules du classeur V20, qui ne sont pas recalculées dans cette interface.")
        path = dossier_path(dossier)
        log_path = path / "corrections.json"
        try:
            logs = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
        except (ValueError, OSError):
            logs = []
        corrected_paths = {log.get("champ") for log in logs if isinstance(log, dict)}
        unit_col, decimal_col = st.columns([2, 1])
        with unit_col:
            unit = st.radio("Unité d'affichage", ["KDZD", "DZD"], horizontal=True, key="financial_display_unit")
        with decimal_col:
            decimals = st.selectbox("Décimales", [0, 2, 3], index=1, key="financial_decimals")
        valid_counts = {
            table: sum(1 for values in records[table].values() for item in values.values()
                       if item["value"] is not None)
            for table in SHEET_COLUMNS
        }
        a, b, c, d = st.columns(4)
        a.metric("Champs ACTIF", valid_counts["ACTIF"])
        b.metric("Champs PASSIF", valid_counts["PASSIF"])
        c.metric("Champs TCR", valid_counts["TCR"])
        d.metric("Corrections", len(logs))
        st.markdown(
            '<div class="yr-legend">'
            '<span><i class="yr-dot" style="background:#FFF8E1"></i>Valeur saisissable dans V20</span>'
            '<span><i class="yr-dot" style="background:#EAF5EF"></i>Regroupement</span>'
            '<span><i class="yr-dot" style="background:#C6E5D4"></i>Sous-total</span>'
            '<span><i class="yr-dot" style="background:#00573F"></i>Total</span>'
            '<span>ƒ Formule Excel · contour ocre = correction</span>'
            '</div>', unsafe_allow_html=True,
        )
        if conflicts:
            st.error(f"{len(conflicts)} lecture(s) contradictoire(s) entre pages pour un même champ ; "
                     "la première lecture non vide reste affichée.")
            with st.expander("Détails des conflits de lecture"):
                st.dataframe(conflicts, use_container_width=True, hide_index=True)
        active_tabs = st.tabs(["ACTIF", "PASSIF", "TCR"])
        for table, panel in zip(SHEET_COLUMNS, active_tabs):
            with panel:
                if not records[table]:
                    st.info(f"Aucune rubrique {table} reconnue dans le JSON chargé. "
                            "La grille V20 est affichée sans valeurs.")
                st.markdown(_render_financial_grid(table, records[table], corrected_paths, unit, decimals),
                            unsafe_allow_html=True)
                st.caption("Une case vide signifie « non extrait / absent » et non zéro. "
                           "Les montants ƒ restent les valeurs lues dans le PDF, pas des formules calculées.")
                _financial_edit_form(table, records[table], data, dossier)
        with st.expander("Audit technique — JSON de travail"):
            st.json(data, expanded=False)
            if logs:
                st.markdown("**Journal des corrections**")
                st.dataframe(logs, use_container_width=True, hide_index=True)


with validation_tab:
    st.subheader("Validation métier")
    dossier = st.session_state.dossier
    if dossier is None or st.session_state.edited is None:
        st.info("La validation exige un dossier et un JSON financier.")
    else:
        st.error("Validation financière définitive et génération Excel désactivées : les contrôles V29d ne sont pas encore intégrés à l'interface.")
        st.download_button("Télécharger le JSON de travail (NON VALIDÉ)",
                           json.dumps(st.session_state.edited, ensure_ascii=False, indent=2),
                           file_name="yarisk_travail_non_valide.json", mime="application/json")
        st.button("Valider définitivement", disabled=True)
        st.button("Générer Excel V20", disabled=True)

with archive_tab:
    st.subheader("Dossiers enregistrés")
    st.caption(f"Répertoire : {ROOT}")
    entries = []
    for f in sorted((ROOT / "dossiers").glob("*/*/dossier.json")) if (ROOT / "dossiers").exists() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            entries.append({"Client": d["client"].get("raison_sociale"), "Identifiant": d["client"].get("identifiant_national"),
                            "Exercice": d.get("exercice"), "Exécution": d.get("execution_id"), "Statut": d.get("validation", {}).get("statut")})
        except (ValueError, KeyError):
            continue
    st.dataframe(entries, use_container_width=True, hide_index=True)
    if not PERSISTENT:
        st.warning("Ces archives ne sont pas garanties persistantes sur Domino sans montage d'un volume ou Dataset approuvé.")

st.divider()
st.caption("Démo technique mono-utilisateur. Aucune authentification métier, isolation multi-utilisateur ni traitement IA automatique dans cette version.")
