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

st.set_page_config(page_title="Ya-Risk | Démo V3.1", page_icon="📊", layout="wide")
st.title("Ya-Risk | Analyse financière")
st.caption("Pilote mono-opérateur · bilan ACTIF / PASSIF / TCR selon le modèle V20 · comparaison pluriannuelle · moteur V29d à connecter")

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
/* Alerte localisée : rouge limité aux valeurs réellement divergentes. */
.yr-sheet td.yr-anomaly, .yr-sheet .yr-total td.yr-anomaly,
.yr-sheet .yr-group td.yr-anomaly, .yr-sheet .yr-section td.yr-anomaly {
    color: #AD1820 !important;
    background: #FFF1F1 !important;
    font-weight: 700;
    box-shadow: inset 0 0 0 2px #D23942;
    cursor: help;
}
.yr-sheet .yr-anomaly-text { color: #AD1820; }
.yr-sheet .yr-anomaly-icon {
    display:inline-block; margin-left: 6px; color:#AD1820;
    font-weight:700; font-size:12px; cursor:help;
    border:1px solid #B72B34; border-radius:50%; width:15px;
    height:15px; line-height:13px; text-align:center;
}
.yr-sheet td.yr-anomaly:focus-visible { outline: 3px solid #D23942; outline-offset: -3px; }
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
        return ""
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


# Gestion pluriannuelle : une liasse PDF = un exercice N et éventuellement N-1.
# Aucun PDF n'est traité dans l'application : les montants viennent exclusivement du JSON associé.
ANNUAL_COLUMNS = {
    "ACTIF": [("Brut", "brut"), ("Amort. / provisions", "amort"), ("Net", "net")],
    "PASSIF": [("Montant", "montant")],
    "TCR": [("Débit", "debit"), ("Crédit", "credit")],
}
SOURCE_COLUMNS = {
    "ACTIF": {"N": {"montant_brut": "brut", "amortissements_provisions_pertes": "amort", "net_n": "net"},
              "N-1": {"net_n1": "net"}},
    "PASSIF": {"N": {"n": "montant"}, "N-1": {"n1": "montant"}},
    "TCR": {"N": {"n_debit": "debit", "n_credit": "credit"},
            "N-1": {"n1_debit": "debit", "n1_credit": "credit"}},
}


def _year(value):
    if isinstance(value, int) and not isinstance(value, bool) and 1900 <= value <= 2100:
        return value
    if value is None:
        return None
    match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", str(value))
    return int(match.group(1)) if match else None


def _date_iso(value):
    """Normalise les seules dates explicites ; jamais de 31/12 inventé."""
    if not value:
        return ""
    if isinstance(value, (datetime, date)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y.%m.%d",
                "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def _friendly_date(value):
    d = _date_iso(value)
    return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y") if d else "Non renseignée"


def _identity_from_json(data):
    if not isinstance(data, dict):
        return {}
    ident = data.get("identite")
    return ident if isinstance(ident, dict) else {}


def _document_year_from_json(data):
    identity = _identity_from_json(data)
    return _year(identity.get("annee")) or _year(identity.get("exercice_au")) or _year(identity.get("exercice"))


def _documents(dossier):
    docs = dossier.get("documents")
    if isinstance(docs, list):
        return docs
    # Compatibilité des dossiers V1/V2, sans déplacement ni remplacement de fichiers.
    legacy = dossier.get("document")
    if not isinstance(legacy, dict):
        return []
    return [{
        "id": "legacy", "pdf_name": legacy.get("nom_original", "source.pdf"),
        "sha256": legacy.get("sha256"), "exercice": dossier.get("exercice"),
        "date_debut": dossier.get("date_debut", ""), "date_fin": dossier.get("date_fin", ""),
        "pdf_path": "source.pdf", "json_original_path": "extraction_originale.json",
        "json_corrige_path": "extraction_corrigee.json", "log_path": "corrections.json",
        "json_name": (dossier.get("extraction") or {}).get("source"),
    }]


def _document_file(dossier, doc, which):
    # Ne jamais accepter de traversée hors du dossier métier.
    rel = doc.get(which)
    if not rel or not isinstance(rel, str):
        return None
    base = dossier_path(dossier).resolve()
    dest = (base / rel).resolve()
    if not dest.is_relative_to(base):
        raise ValueError("Chemin de fichier invalide dans le dossier")
    return dest


def _load_document_json(dossier, doc):
    for prop in ("json_corrige_path", "json_original_path"):
        path = _document_file(dossier, doc, prop)
        if path is not None and path.is_file():
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(obj, dict):
                    return obj
            except (OSError, ValueError):
                continue
    return None


def _load_document_logs(dossier, doc):
    path = _document_file(dossier, doc, "log_path")
    if path is not None and path.is_file():
        try:
            logs = json.loads(path.read_text(encoding="utf-8"))
            return logs if isinstance(logs, list) else []
        except (OSError, ValueError):
            pass
    return []


def _read_json_upload(obj):
    data = json.loads(obj.getvalue())
    if not isinstance(data, dict):
        raise ValueError(f"{obj.name} : la racine du JSON doit être un objet")
    return data


def _guess_json_for_pdf(pdf_name, json_assets):
    """Association implicite seulement sur stem EXACT et unique (sans suffixe .json)."""
    stem = Path(pdf_name).stem.casefold()
    pdf_full = Path(pdf_name).name.casefold()
    candidates = [name for name in json_assets
                  if Path(name).stem.casefold() in (stem, pdf_full)]
    return candidates[0] if len(candidates) == 1 else None


def _merge_yearly(dossier, doc_data):
    """Compare les valeurs de toutes les liasses, avec priorité à N sur N-1.

    En cas de divergence, l'affichage n'en masque pas l'existence et indique la source choisie.
    Les années N sont visibles même si aucun JSON n'est encore présent.
    """
    data = {table: {} for table in SHEET_LAYOUT}
    warnings = []
    years = set()
    close_dates = {}
    sources = {}
    local_conflicts = []
    for doc, financial in doc_data:
        year = _year(doc.get("exercice"))
        if year is None:
            continue
        years.add(year)
        close = _date_iso(doc.get("date_fin"))
        if close:
            if year in close_dates and close_dates[year] != close:
                warnings.append({"Type": "Dates de clôture différentes", "Exercice": year,
                                 "Document": doc.get("pdf_name"), "Valeurs": close_dates[year] + " / " + close})
            else:
                close_dates[year] = close
        sources.setdefault(year, []).append(doc.get("pdf_name", "PDF"))
        if not isinstance(financial, dict):
            continue
        records, clashes = _collect_financial_data(financial)
        for conflict in clashes:
            conflict.update({"pdf": doc.get("pdf_name"), "document_id": doc["id"],
                             "exercice_n": year})
            local_conflicts.append(conflict)
        for table, rows in records.items():
            for row_id, values in rows.items():
                for source_col, item in values.items():
                    if item.get("value") is None:
                        continue
                    period = "N-1" if source_col.startswith("n1") or source_col == "net_n1" else "N"
                    target_year = year if period == "N" else year - 1
                    dest_col = SOURCE_COLUMNS[table][period].get(source_col)
                    if not dest_col:
                        continue
                    years.add(target_year)
                    r = {
                        **item, "doc_id": doc["id"], "pdf_name": doc.get("pdf_name", ""),
                        "source_col": source_col, "source_period": period,
                        "priority": 2 if period == "N" else 1,
                        "formula": source_col in FORMULA_COLUMNS[table].get(row_id, []),
                        "year": target_year, "table": table, "row_id": row_id,
                    }
                    dest = data[table].setdefault(target_year, {}).setdefault(row_id, {})
                    prev = dest.get(dest_col)
                    if prev is None:
                        dest[dest_col] = r
                    else:
                        chosen, other = (r, prev) if r["priority"] > prev["priority"] else (prev, r)
                        if prev["value"] != r["value"]:
                            warnings.append({"Type": "Écart de montant", "Exercice": target_year,
                                             "Tableau": table, "Rubrique": row_id,
                                             "Colonne": dest_col, "Retenu": chosen["value"], "Autre": other["value"],
                                             "Source retenue": chosen["pdf_name"], "Autre source": other["pdf_name"],
                                             "Période retenue": chosen["source_period"],
                                             "Période autre": other["source_period"],
                                             "Page retenue": chosen.get("page"),
                                             "Autre page": other.get("page")})
                        if r["priority"] > prev["priority"]:
                            dest[dest_col] = r
    return data, sorted(years), close_dates, sources, warnings, local_conflicts


def _amount_for_anomaly(value):
    """Représentation fidèle d'un montant source, affiché avec son unité DZD."""
    if not _scalar_number(value):
        return "non renseigné"
    return _display_amount(value, "DZD", 0 if float(value).is_integer() else 2) + " DZD"


def _anomaly_index(disputes, page_disputes):
    """Associe chaque divergence *constatée* à sa cellule ACTIF/PASSIF/TCR.

    Une absence d'extraction ou une cellule à formule non calculée n'est pas
    assimilée automatiquement à une anomalie sans règle de contrôle établie.
    """
    result = {}
    for issue in disputes:
        if issue.get("Type") != "Écart de montant":
            continue
        table, yr, row, col = (issue.get("Tableau"), issue.get("Exercice"),
                               issue.get("Rubrique"), issue.get("Colonne"))
        if table not in ANNUAL_COLUMNS or not isinstance(yr, int) or not row or not col:
            continue
        name1, name2 = issue.get("Source retenue", "PDF inconnu"), issue.get("Autre source", "PDF inconnu")
        period1, period2 = issue.get("Période retenue", "N"), issue.get("Période autre", "N-1")
        p1, p2 = issue.get("Page retenue"), issue.get("Autre page")
        source1 = f"{name1} ({period1}{', page ' + str(p1) if p1 else ''})"
        source2 = f"{name2} ({period2}{', page ' + str(p2) if p2 else ''})"
        reason = ("ANOMALIE : montants différents pour le même poste et le même exercice.\n"
                  f"Valeur affichée : {_amount_for_anomaly(issue.get('Retenu'))} — {source1}.\n"
                  f"Autre valeur : {_amount_for_anomaly(issue.get('Autre'))} — {source2}.\n"
                  "Action : comparer les deux PDF et confirmer le montant correct.")
        result.setdefault((table, yr, row, col), []).append(reason)

    for issue in page_disputes:
        table, col, row = (issue.get("table"), issue.get("column"), issue.get("row"))
        year = _year(issue.get("exercice_n"))
        if table not in SOURCE_COLUMNS or year is None or row is None or col is None:
            continue
        period = "N-1" if col.startswith("n1") or col == "net_n1" else "N"
        dest_col = SOURCE_COLUMNS[table][period].get(col)
        if dest_col is None:
            continue
        target_year = year - 1 if period == "N-1" else year
        msg = ("ANOMALIE : lectures contradictoires dans un même PDF.\n"
               f"Document : {issue.get('pdf', 'PDF inconnu')} — exercice {target_year}.\n"
               f"Page {issue.get('first_page', '?')} : {_amount_for_anomaly(issue.get('first'))}.\n"
               f"Page {issue.get('other_page', '?')} : {_amount_for_anomaly(issue.get('other'))}.\n"
               "Action : consulter les pages concernées et vérifier la valeur à retenir.")
        result.setdefault((table, target_year, row, dest_col), []).append(msg)
    return result


def _render_multiyear_grid(table, merged, years, close_dates, corrected, unit="KDZD", decimals=2,
                           start_dates=None, anomalies=None):
    per_year = ANNUAL_COLUMNS[table]
    start_dates = start_dates or {}
    anomalies = anomalies or {}
    parts = [FINANCIAL_CSS, '<div class="yr-wrap"><table class="yr-sheet yr-multi"><thead><tr>',
             '<th class="yr-top yr-label" rowspan="2">Rubriques / postes financiers</th>']
    for year in years:
        begins, closes = start_dates.get(year), close_dates.get(year)
        if begins and closes:
            interval = f"Du {_friendly_date(begins)} au {_friendly_date(closes)}"
        elif closes:
            interval = f"Arrêté : {_friendly_date(closes)}"
        elif begins:
            interval = f"Début : {_friendly_date(begins)} · clôture non renseignée"
        else:
            interval = "Dates non renseignées"
        stamp = f'<span class="yr-date">{html.escape(interval)}</span>'
        parts.append(f'<th class="yr-top" colspan="{len(per_year)}">Exercice {year}{stamp}</th>')
    parts.append('</tr><tr>')
    for year in years:
        for label, _key in per_year:
            parts.append(f'<th class="yr-second">{html.escape(label)} ({html.escape(unit)})</th>')
    parts.append('</tr></thead><tbody>')
    for row_num, row_id, label, kind, indented in SHEET_LAYOUT[table]:
        pad = ' yr-indent' if indented else ''
        parts.append(f'<tr class="yr-{kind}"><td class="yr-label{pad}" title="Ligne Excel {row_num}">{html.escape(label)}</td>')
        for year in years:
            for _label, col in per_year:
                item = merged.get(year, {}).get(row_id, {}).get(col) if row_id else None
                v = item["value"] if item is not None else None
                formula = bool(item and item.get("formula"))
                cell_class = 'yr-formula' if formula else 'yr-input'
                changed = bool(item and (item["doc_id"], item["path"]) in corrected)
                hint = f"Exercice {year}. "
                if item:
                    hint += f"Source : {item['pdf_name']} · colonne {item['source_period']}. "
                    if item.get("page"):
                        hint += f"Page PDF {item['page']}. "
                    if formula:
                        hint += "Cellule à formule dans Excel V20, non recalculée ici. "
                    if changed:
                        hint += "Montant corrigé et historisé."
                else:
                    hint += "Aucune valeur extraite."
                issues = anomalies.get((table, year, row_id, col), []) if row_id else []
                # Les montants divergents sont en rouge et expliqués au survol.
                if issues:
                    hint = "\n\n".join(issues) + "\n\n" + hint
                aria_tip = html.escape(hint, quote=True).replace("\n", "&#10;")
                suffix = '<span class="yr-fn">ƒ</span>' if formula and v is not None else ''
                mark = ('<span class="yr-anomaly-icon" aria-hidden="true">i</span>'
                        if issues else '')
                anomaly_class = ' yr-anomaly' if issues else ''
                extra = f' tabindex="0" aria-label="{aria_tip}"' if issues else ''
                parts.append(f'<td class="yr-val {cell_class}{anomaly_class}'
                             f'{" yr-changed" if changed else ""}{" yr-empty" if v is None else ""}"'
                             f' title="{aria_tip}"{extra}>'
                             f'{_display_amount(v, unit, decimals)}{mark}{suffix}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div>')
    return ''.join(parts)


def _edit_merged_year(table, merged, years, dossier, documents, data_by_id):
    eligible = []
    labels = {id_: label for _num, id_, label, _kind, _indent in SHEET_LAYOUT[table] if id_}
    for year in years:
        for row_id, cols in merged.get(year, {}).items():
            for col, item in cols.items():
                if not item.get("formula") and item.get("path") and item["doc_id"] in data_by_id:
                    eligible.append((year, row_id, col, item))
    if not eligible:
        st.caption("Aucun champ modifiable pour cet état.")
        return
    with st.expander(f"Corriger un montant — {table}", expanded=False):
        st.caption("Modification dans la source JSON du PDF choisi, en DZD. Cellules Excel à formule non éditables.")
        options = list(range(len(eligible)))
        i = st.selectbox("Exercice / rubrique / colonne / fichier", options,
                         format_func=lambda j: f"{eligible[j][0]} | {labels.get(eligible[j][1], eligible[j][1])} | "
                                               f"{eligible[j][2]} | {eligible[j][3]['pdf_name']}",
                         key=f"edit_year_{table}")
        yr, row_id, col_id, item = eligible[i]
        doc = documents[item["doc_id"]]
        source_json = data_by_id[item["doc_id"]]
        with st.form(f"edit_multi_{table}_{doc['id']}_{yr}_{row_id}_{col_id}"):
            new_value = st.text_input("Montant corrigé (DZD)", value=str(item["value"]))
            justification = st.text_area("Justification obligatoire", max_chars=1000)
            submitted = st.form_submit_button("Enregistrer et historiser")
        if submitted:
            if not justification.strip():
                st.error("La justification est obligatoire.")
                return
            try:
                numeric = _parse_dzd_amount(new_value)
                if numeric == item["value"]:
                    st.info("La valeur est inchangée.")
                    return
                updated = copy.deepcopy(source_json)
                assign_path(updated, item["path"], numeric)
                output = _document_file(dossier, doc, "json_corrige_path")
                log_file = _document_file(dossier, doc, "log_path")
                logs = _load_document_logs(dossier, doc)
                logs.append({"date": now(), "exercice": yr, "pdf": doc["pdf_name"],
                             "table": table, "rubrique": row_id, "colonne": col_id,
                             "champ": item["path"], "avant": item["value"], "apres": numeric,
                             "motif": justification.strip(), "unite": "DZD"})
                atomic_json(output, updated)
                atomic_json(log_file, logs)
                dossier["validation"] = {"statut": "non_valide"}
                atomic_json(dossier_path(dossier) / "dossier.json", dossier)
                st.session_state.dossier = dossier
                st.success("Correction historisée. Validation métier non réalisée.")
                st.rerun()
            except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
                st.error(f"Correction impossible : {exc}")


def _save_dates(dossier, documents, doc_id, debut, fin):
    """Complète la fiche d'un document importé, y compris les dossiers V2."""
    debut_iso, fin_iso = _date_iso(debut), _date_iso(fin)
    if (debut.strip() and not debut_iso) or (fin.strip() and not fin_iso):
        raise ValueError("Dates attendues au format AAAA-MM-JJ ou JJ/MM/AAAA")
    if debut_iso and fin_iso and debut_iso > fin_iso:
        raise ValueError("La date de début dépasse la date de clôture")
    d = next(d for d in documents if d["id"] == doc_id)
    if fin_iso and _year(fin_iso) != _year(d.get("exercice")):
        raise ValueError("La date de clôture doit appartenir à l'exercice de ce PDF")
    old = {"date_debut": d.get("date_debut", ""), "date_fin": d.get("date_fin", "")}
    if old == {"date_debut": debut_iso, "date_fin": fin_iso}:
        return False
    log_file = dossier_path(dossier) / "historique_dates.json"
    logs = json.loads(log_file.read_text(encoding="utf-8")) if log_file.is_file() else []
    logs.append({"date": now(), "pdf": d["pdf_name"], "document_id": doc_id,
                 "avant": old, "apres": {"date_debut": debut_iso, "date_fin": fin_iso}})
    d["date_debut"], d["date_fin"] = debut_iso, fin_iso
    dossier["documents"] = documents
    dossier["validation"] = {"statut": "non_valide"}
    atomic_json(log_file, logs)
    atomic_json(dossier_path(dossier) / "dossier.json", dossier)
    return True


FINANCIAL_CSS += """
<style>
.yr-sheet.yr-multi {min-width:max-content;}
.yr-sheet.yr-multi .yr-label {min-width:320px; width:320px; max-width:320px;}
.yr-sheet.yr-multi .yr-val {min-width:150px;}
.yr-date {display:block; font-weight:400; font-size:10px; margin-top:3px; opacity:.95;}
</style>
"""
if "dossier" not in st.session_state:
    st.session_state.dossier = None
if "edited" not in st.session_state:
    st.session_state.edited = None  # Compatibilité de session V2 ; les données sont relues sur disque.
# Restaurer les widgets avant leur création. Streamlit interdit de les réécrire après affichage.
restore_client = st.session_state.pop("_pending_restore_client", None)
if isinstance(restore_client, dict):
    for key, _label in FIELDS:
        raw_value = restore_client.get(key, "")
        st.session_state[f"field_{key}"] = str(raw_value) if raw_value is not None else ""
    st.session_state["field_observations"] = str(restore_client.get("observations") or "")

client_tab, import_tab, results_tab, validation_tab, archive_tab = st.tabs([
    "1 · Fiche client", "2 · Import multi-PDF", "3 · Bilan pluriannuel", "4 · Validation", "5 · Archive"
])

with client_tab:
    st.subheader("Identification et profil client")
    st.info("Identifiant national et raison sociale obligatoires. Un dossier peut contenir plusieurs exercices.")
    with st.form("client_form"):
        cols = st.columns(2)
        for i, (key, label) in enumerate(FIELDS):
            with cols[i % 2]:
                if key in TRISTATE:
                    st.selectbox(label, ["Non renseigné", "Oui", "Non"], key=f"field_{key}")
                else:
                    st.text_input(label + (" (AAAA-MM-JJ)" if key == "date_derniere_revue_annuelle" else ""),
                                  key=f"field_{key}")
        st.text_area("Précisions sur les particularités ou incidents", key="field_observations")
        if st.form_submit_button("Enregistrer la fiche dans la session"):
            st.success("Fiche enregistrée dans la session. Vous pouvez importer plusieurs liasses.")

with import_tab:
    st.subheader("Import des liasses d'un même client")
    st.caption("Importer un PDF par exercice, avec son JSON V29d si disponible. "
               "Chaque PDF reste indépendant et ses dates sont conservées.")
    client = {key: st.session_state.get(f"field_{key}", "") for key, _ in FIELDS}
    client["observations"] = st.session_state.get("field_observations", "")
    client_id = client["identifiant_national"].strip()
    all_archives = []
    if client_id:
        for manifest in sorted((ROOT / "dossiers" / safe_id(client_id)).glob("*/dossier.json")):
            try:
                previous = json.loads(manifest.read_text(encoding="utf-8"))
                if previous.get("client", {}).get("identifiant_national") == client_id:
                    all_archives.append(previous)
            except (OSError, ValueError, TypeError):
                continue
    choices = ["Créer un nouveau dossier"]
    by_choice = {}
    for old in all_archives:
        label = f"Compléter le dossier {old['execution_id'][:10]} ({len(_documents(old))} PDF)"
        choices.append(label)
        by_choice[label] = old
    if st.session_state.dossier and st.session_state.dossier.get("client", {}).get("identifiant_national") == client_id:
        current_label = next((k for k, d in by_choice.items()
                              if d["execution_id"] == st.session_state.dossier["execution_id"]), None)
        default_mode = choices.index(current_label) if current_label else 0
    else:
        default_mode = 0
    mode = st.selectbox("Destination des nouveaux PDF", choices, index=default_mode, key="import_mode")
    pdf_files = st.file_uploader("Liasses fiscales PDF (plusieurs fichiers)", type=["pdf"],
                                 accept_multiple_files=True, key="pdf_batch")
    json_files = st.file_uploader("JSON V29d correspondants (facultatif, plusieurs fichiers)",
                                  type=["json"], accept_multiple_files=True, key="json_batch")
    json_assets = {}
    json_errors = []
    for upload in json_files or []:
        try:
            if upload.name in json_assets:
                raise ValueError("Plusieurs JSON portent le même nom")
            json_assets[upload.name] = _read_json_upload(upload)
        except (ValueError, UnicodeDecodeError) as exc:
            json_errors.append(f"{upload.name} : {exc}")
    for error in json_errors:
        st.error(error)

    prepared = []
    if pdf_files:
        st.markdown("#### Association et dates des exercices")
        st.caption("Les dates de clôture du JSON sont proposées si présentes ; elles ne sont jamais supposées au 31 décembre.")
    for i, upload in enumerate(pdf_files or []):
        raw = upload.getvalue()
        sha = hashlib.sha256(raw).hexdigest()
        key = f"{i}_{sha[:12]}"
        guess = _guess_json_for_pdf(upload.name, json_assets)
        # Le choix reste explicite si la correspondance par nom ne peut être établie.
        candidates = ["Aucun JSON (PDF archivé, extraction non exécutée)"] + list(json_assets)
        default = candidates.index(guess) if guess in candidates else 0
        with st.expander(f"{i+1}. {upload.name}", expanded=True):
            selected = st.selectbox("JSON associé à ce PDF", candidates, index=default,
                                    key=f"assoc_{key}")
            financial = json_assets.get(selected)
            identity = _identity_from_json(financial)
            source_year = _document_year_from_json(financial)
            filename_year = _year(Path(upload.name).stem)
            presumed_year = source_year or filename_year or date.today().year
            year = st.number_input("Exercice N (année d'arrêté du bilan)", min_value=1900, max_value=2100,
                                   value=presumed_year, step=1, key=f"year_{key}")
            if source_year and int(year) != source_year:
                st.error(f"L'année choisie ({year}) ne correspond pas à celle du JSON ({source_year}).")
            elif not source_year:
                st.caption("Exercice non certifié par un JSON : confirmer l'année à partir du PDF.")
            confirmed = True
            if not source_year:
                confirmed = st.checkbox("J'ai vérifié l'exercice N sur la liasse PDF",
                                        key=f"confirm_year_{key}")
            c1, c2 = st.columns(2)
            with c1:
                start_date = st.text_input("Début de l'exercice (AAAA-MM-JJ)",
                                           value=_date_iso(identity.get("exercice_du")), key=f"start_{key}")
            with c2:
                end_date = st.text_input("Date d'arrêté / clôture (AAAA-MM-JJ)",
                                         value=_date_iso(identity.get("exercice_au")), key=f"end_{key}")
            if not financial:
                st.caption("Sans JSON : la liasse sera enregistrée, mais aucun montant ne sera inventé.")
        prepared.append({"upload": upload, "raw": raw, "sha": sha,
                         "year": int(year), "start": start_date.strip(), "end": end_date.strip(),
                         "json": financial, "json_name": selected if financial is not None else None,
                         "source_year": source_year, "confirmed": confirmed})

    if st.button("Enregistrer les liasses dans le dossier", type="primary", disabled=not bool(prepared)):
        if not client_id or not client["raison_sociale"].strip():
            st.error("Renseigner l'identifiant national et la raison sociale dans l'onglet 1.")
        elif json_errors:
            st.error("Corriger les JSON invalides avant l'import.")
        else:
            errors = []
            picked = [x["json_name"] for x in prepared if x["json_name"]]
            if len(picked) != len(set(picked)):
                errors.append("Un même JSON a été associé à plusieurs PDF : choisissez un JSON distinct par liasse.")
            if len({x["sha"] for x in prepared}) != len(prepared):
                errors.append("Un même PDF est présent plusieurs fois dans la sélection.")
            target = by_choice.get(mode)
            known_sha = {d.get("sha256") for d in _documents(target)} if target else set()
            for item in prepared:
                if not item["raw"].startswith(b"%PDF-"):
                    errors.append(f"{item['upload'].name} : signature PDF non reconnue.")
                if item["sha"] in known_sha:
                    errors.append(f"{item['upload'].name} : PDF déjà présent dans le dossier.")
                if item["source_year"] is not None and item["year"] != item["source_year"]:
                    errors.append(f"{item['upload'].name} : année déclarée différente du JSON V29d.")
                if not item["confirmed"]:
                    errors.append(f"{item['upload'].name} : confirmez l'année du PDF avant l'import.")
                start_iso = _date_iso(item["start"])
                end_iso = _date_iso(item["end"])
                if (item["start"] and not start_iso) or (item["end"] and not end_iso):
                    errors.append(f"{item['upload'].name} : date invalide (AAAA-MM-JJ ou JJ/MM/AAAA).")
                if start_iso and end_iso and start_iso > end_iso:
                    errors.append(f"{item['upload'].name} : début postérieur à la clôture.")
                if end_iso and _year(end_iso) != item["year"]:
                    errors.append(f"{item['upload'].name} : la clôture n'est pas dans l'année N indiquée.")
            if errors:
                for err in errors:
                    st.error(err)
            else:
                if target is None:
                    target = {"schema_version": "yarisk-demo-v3", "execution_id": uuid.uuid4().hex,
                              "created_at": now(), "client": client, "documents": [],
                              "validation": {"statut": "non_valide"}}
                else:
                    target = copy.deepcopy(target)
                    # Conversion transparente des anciens dossiers avec chemins conservés.
                    target["documents"] = copy.deepcopy(_documents(target))
                    target["schema_version"] = "yarisk-demo-v3"
                destination = dossier_path(target)
                destination.mkdir(parents=True, exist_ok=True)
                try:
                    for item in prepared:
                        doc_id = uuid.uuid4().hex
                        doc_dir = destination / "documents" / doc_id
                        doc_dir.mkdir(parents=True, exist_ok=False)
                        (doc_dir / "source.pdf").write_bytes(item["raw"])
                        if item["json"] is not None:
                            atomic_json(doc_dir / "extraction_originale.json", item["json"])
                        target["documents"].append({
                            "id": doc_id, "pdf_name": item["upload"].name, "sha256": item["sha"],
                            "exercice": item["year"], "date_debut": _date_iso(item["start"]),
                            "date_fin": _date_iso(item["end"]), "json_name": item["json_name"],
                            "pdf_path": f"documents/{doc_id}/source.pdf",
                            "json_original_path": f"documents/{doc_id}/extraction_originale.json",
                            "json_corrige_path": f"documents/{doc_id}/extraction_corrigee.json",
                            "log_path": f"documents/{doc_id}/corrections.json", "created_at": now(),
                        })
                    target["validation"] = {"statut": "non_valide"}
                    atomic_json(destination / "dossier.json", target)
                    st.session_state.dossier = target
                    st.session_state.edited = None
                    st.success(f"{len(prepared)} PDF enregistré(s) dans le dossier · "
                               f"{len(target['documents'])} liasse(s) au total. Voir l'onglet 3.")
                except (OSError, ValueError, TypeError) as exc:
                    st.error(f"Enregistrement interrompu : {exc}. Vérifier le stockage du projet.")

with results_tab:
    st.subheader("Bilan comparatif — tous les exercices disponibles")
    dossier = st.session_state.dossier
    if dossier is None:
        st.info("Aucun dossier actif. Importez des PDF ou ouvrez un dossier existant depuis l'Archive.")
        for table, tab in zip(SHEET_COLUMNS, st.tabs(["ACTIF", "PASSIF", "TCR"])):
            with tab:
                st.markdown(_render_financial_grid(table, {}, set(), "KDZD", 2), unsafe_allow_html=True)
        st.caption("Structure Excel V20 affichée à vide ; aucune donnée financière fictive.")
    else:
        docs = _documents(dossier)
        doc_data = [(d, _load_document_json(dossier, d)) for d in docs]
        data_by_id = {d["id"]: data for d, data in doc_data if data is not None}
        docs_by_id = {d["id"]: d for d in docs}
        combined, years, close_dates, source_by_year, disputes, page_disputes = _merge_yearly(dossier, doc_data)
        anomalies = _anomaly_index(disputes, page_disputes)
        start_dates = {_year(d.get("exercice")): _date_iso(d.get("date_debut"))
                       for d in docs if _year(d.get("exercice")) and _date_iso(d.get("date_debut"))}
        logs_by_id = {d["id"]: _load_document_logs(dossier, d) for d in docs}
        corrected = {(d_id, log.get("champ")) for d_id, logs in logs_by_id.items()
                     for log in logs if isinstance(log, dict) and log.get("champ")}
        n_corrections = sum(len(logs) for logs in logs_by_id.values())
        st.caption(f"{dossier['client'].get('raison_sociale', 'Client')} · "
                   f"{len(docs)} PDF · {len(years)} années affichées · Référentiel Excel V20")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Exercices", len(years))
        k2.metric("Liasses PDF", len(docs))
        k3.metric("JSON associés", len(data_by_id))
        k4.metric("Corrections", n_corrections)
        st.warning("Lecture documentaire non certifiée. Les colonnes N-1 complètent l'année antérieure ; "
                   "si deux documents diffèrent, l'écart est signalé. ƒ = formule Excel non recalculée.")
        inventory = [{"PDF": d.get("pdf_name"), "Exercice N": d.get("exercice"),
                      "Du": _friendly_date(d.get("date_debut")),
                      "Arrêté / Au": _friendly_date(d.get("date_fin")),
                      "Extraction": "JSON importé (non vérifié)" if d["id"] in data_by_id else "Non exécutée"}
                     for d in docs]
        with st.expander("Inventaire des documents et dates", expanded=True):
            st.dataframe(inventory, use_container_width=True, hide_index=True)
            st.caption("Pour compléter une date manquante après import, utilisez le formulaire ci-dessous.")
            doc_chosen = st.selectbox("Liasse à dater", list(docs_by_id),
                                      format_func=lambda id_: f"{docs_by_id[id_]['exercice']} — {docs_by_id[id_]['pdf_name']}",
                                      key=f"date_doc_{dossier['execution_id']}") if docs else None
            if doc_chosen:
                chosen = docs_by_id[doc_chosen]
                with st.form(f"metadata_{dossier['execution_id']}_{doc_chosen}"):
                    aa, bb = st.columns(2)
                    with aa:
                        new_start = st.text_input("Début (AAAA-MM-JJ)", value=chosen.get("date_debut") or "")
                    with bb:
                        new_end = st.text_input("Clôture / arrêté (AAAA-MM-JJ)", value=chosen.get("date_fin") or "")
                    save_dates = st.form_submit_button("Enregistrer les dates")
                if save_dates:
                    try:
                        changed = _save_dates(dossier, docs, doc_chosen, new_start, new_end)
                        st.session_state.dossier = dossier
                        if changed:
                            st.success("Dates mises à jour et historisées.")
                            st.rerun()
                        else:
                            st.info("Aucune modification.")
                    except (ValueError, OSError, StopIteration) as exc:
                        st.error(f"Dates non enregistrées : {exc}")
        left, right = st.columns([2, 1])
        with left:
            unit = st.radio("Unité d'affichage", ["KDZD", "DZD"], horizontal=True,
                            key="financial_display_unit")
        with right:
            decimals = st.selectbox("Décimales", [0, 2, 3], index=1, key="financial_decimals")
        if disputes:
            st.error(f"{len(disputes)} divergence(s) entre les PDF : priorité aux valeurs de l'année N "
                     "de leur propre document, sinon première valeur disponible.")
            with st.expander("Voir les divergences entre exercices et sources"):
                st.dataframe(disputes, use_container_width=True, hide_index=True)
        if page_disputes:
            st.error(f"{len(page_disputes)} divergence(s) entre pages d'un même PDF.")
            with st.expander("Voir les divergences de lecture internes"):
                st.dataframe(page_disputes, use_container_width=True, hide_index=True)
        st.markdown('<div class="yr-legend"><span><i class="yr-dot" style="background:#FFF8E1"></i>'
                    'Données source</span><span><i class="yr-dot" style="background:#EAF5EF"></i>'
                    'Regroupement</span><span><i class="yr-dot" style="background:#C6E5D4"></i>'
                    'Sous-total</span><span><i class="yr-dot" style="background:#00573F"></i>'
                    'Total</span><span><i class="yr-dot" style="background:#FFF1F1;border-color:#D23942"></i>'
                    'Montant rouge + i : anomalie expliquée au survol</span>'
                    '<span>ƒ Formule · contour ocre : correction</span></div>', unsafe_allow_html=True)
        for table, tab in zip(SHEET_COLUMNS, st.tabs(["ACTIF", "PASSIF", "TCR"])):
            with tab:
                if years:
                    st.markdown(_render_multiyear_grid(table, combined[table], years,
                                                      close_dates, corrected, unit, decimals, start_dates, anomalies),
                                unsafe_allow_html=True)
                else:
                    st.info("Aucun exercice pour le moment.")
                st.caption("Texte rouge + i : survoler ou sélectionner la cellule pour lire l'anomalie, "
                           "les montants comparés et les PDF concernés. "
                           "Case vide = donnée non extraite. Défilement horizontal pour toutes les années.")
                _edit_merged_year(table, combined[table], years, dossier, docs_by_id, data_by_id)
        with st.expander("Audit technique — JSON de chaque liasse"):
            if doc_data:
                audit_tabs = st.tabs([f"{d.get('exercice')} · {d.get('pdf_name')}" for d, _ in doc_data])
                for (d, financial), audit_tab in zip(doc_data, audit_tabs):
                    with audit_tab:
                        if financial is None:
                            st.info("PDF enregistré, extraction non connectée.")
                        else:
                            st.json(financial, expanded=False)
                            if logs_by_id.get(d["id"]):
                                st.dataframe(logs_by_id[d["id"]], use_container_width=True, hide_index=True)

with validation_tab:
    st.subheader("Validation métier")
    dossier = st.session_state.dossier
    if dossier is None:
        st.info("Sélectionner ou créer un dossier avant validation.")
    else:
        docs = _documents(dossier)
        data = [(d, _load_document_json(dossier, d)) for d in docs]
        st.error("Validation définitive et génération Excel désactivées : contrôles métier V29d non connectés.")
        st.caption("Les données des exercices restent distinctes ; aucun recalcul n'est réalisé à partir du PDF.")
        if any(financial is not None for _d, financial in data):
            export = {"dossier": dossier, "extractions_non_validees": [
                {"document_id": d["id"], "pdf": d["pdf_name"], "exercice": d["exercice"],
                 "json": financial} for d, financial in data if financial is not None]}
            st.download_button("Télécharger tous les JSON de travail (NON VALIDÉS)",
                               json.dumps(export, ensure_ascii=False, indent=2),
                               file_name="yarisk_multi_exercices_non_valides.json", mime="application/json")
        st.button("Valider définitivement", disabled=True)
        st.button("Générer Excel V20", disabled=True)

with archive_tab:
    st.subheader("Archives des dossiers clients")
    st.caption(f"Répertoire : {ROOT}")
    entries = []
    available = {}
    for manifest in sorted((ROOT / "dossiers").glob("*/*/dossier.json")):
        try:
            old = json.loads(manifest.read_text(encoding="utf-8"))
            docs = _documents(old)
            label = f"{old['client'].get('raison_sociale')} · {old['execution_id'][:10]}"
            available[label] = old
            entries.append({"Client": old["client"].get("raison_sociale"),
                            "Identifiant": old["client"].get("identifiant_national"),
                            "Exercices PDF": ", ".join(map(str, sorted({_year(d.get('exercice')) for d in docs if _year(d.get('exercice'))}))),
                            "PDF": len(docs), "Exécution": old.get("execution_id"),
                            "Statut": old.get("validation", {}).get("statut")})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    st.dataframe(entries, use_container_width=True, hide_index=True)
    if available:
        selection = st.selectbox("Ouvrir un dossier existant", list(available), key="archive_open")
        if st.button("Afficher le dossier dans Bilan"):
            st.session_state.dossier = available[selection]
            st.session_state.edited = None
            st.session_state["_pending_restore_client"] = available[selection].get("client", {})
            st.success("Dossier chargé : consulter l'onglet 3 · Bilan pluriannuel.")
            st.rerun()
    if not PERSISTENT:
        st.warning("Archives potentiellement temporaires sur Domino sans montage de stockage approuvé.")

st.divider()
st.caption("Démo mono-opérateur · import des fichiers sans extraction IA automatique · "
           "états financiers non certifiés · accès et sécurité à valider avant production.")
