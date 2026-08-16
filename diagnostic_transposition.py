#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnostic_transposition.py — Pourquoi le classeur ressort vide ?

Remonte la chaine JSON -> Excel etape par etape et s'arrete a la premiere
rupture, en affichant la structure REELLE de vos fichiers.

Usage :
    python diagnostic_transposition.py <dossier.json> [modele.xlsx]

A executer tel quel dans une cellule du notebook :
    exec(open('diagnostic_transposition.py').read().replace(
        '__CHEMIN__', str(next(JSON_DIR.glob('*.json')))))
"""
import json
import sys
from pathlib import Path


def _titre(txt):
    print()
    print('=' * 74)
    print(txt)
    print('=' * 74)


def _type_court(v):
    if isinstance(v, dict):
        return 'dict(' + str(len(v)) + ')'
    if isinstance(v, list):
        return 'list(' + str(len(v)) + ')'
    return type(v).__name__


def diagnostiquer(chemin_json, mapping=None):
    doc = json.loads(Path(chemin_json).read_text(encoding='utf-8'))

    # ── ETAPE 1 : structure du document ─────────────────────────────────
    _titre('ETAPE 1 — Structure du document')
    print('Fichier          : ' + Path(chemin_json).name)
    print('Cles racine      : ' + ', '.join(sorted(doc.keys())))
    print('schema_version   : ' + str(doc.get('schema_version')))
    pages = doc.get('pages')
    if not isinstance(pages, list) or not pages:
        print()
        print('>>> RUPTURE : aucune liste "pages" exploitable.')
        print('    La transposition lit doc["pages"]. Verifiez que le JSON')
        print('    provient bien de la cellule 10 du pipeline.')
        return
    print('Nombre de pages  : ' + str(len(pages)))

    # ── ETAPE 2 : ou sont les donnees ? ─────────────────────────────────
    _titre('ETAPE 2 — Emplacement des donnees dans les pages')
    sans_donnees, avec_donnees = [], []
    for p in pages:
        d = p.get('donnees')
        if isinstance(d, dict) and any(
                k not in ('brut', 'AUTRE') and v not in (None, {}, [])
                for k, v in d.items()):
            avec_donnees.append(p)
        else:
            sans_donnees.append(p)

    print('Pages avec donnees exploitables : ' + str(len(avec_donnees)))
    print('Pages sans donnees              : ' + str(len(sans_donnees)))

    if not avec_donnees:
        print()
        print('>>> RUPTURE : aucune page ne porte de donnees.')
        p0 = pages[0]
        print('    Cles de la premiere page : ' + ', '.join(sorted(p0.keys())))
        d0 = p0.get('donnees')
        print('    Type de page["donnees"]  : ' + _type_court(d0))
        if isinstance(d0, dict):
            for k, v in list(d0.items())[:8]:
                print('       ' + str(k) + ' -> ' + _type_court(v))
        print()
        print('    Cause la plus probable : l extraction VLM a echoue et')
        print('    "donnees" ne contient que la cle "brut". Regardez')
        print('    page["statut_extraction"] :')
        for p in pages[:6]:
            st = p.get('statut_extraction') or {}
            print('       ' + str(p.get('page_id')) + ' : '
                  + str(st.get('statut')) + ' | champs='
                  + str(st.get('nb_champs_extraits')))
        return

    # ── ETAPE 3 : forme de chaque bloc ──────────────────────────────────
    _titre('ETAPE 3 — Forme reelle des blocs de donnees')
    formes = {}
    for p in avec_donnees:
        for tab, bloc in (p.get('donnees') or {}).items():
            if tab in ('brut', 'AUTRE') or bloc in (None, {}, []):
                continue
            if isinstance(bloc, list):
                forme = 'liste plate (tableau dynamique)'
            elif isinstance(bloc, dict) and isinstance(bloc.get('lignes'), list):
                forme = "dict avec cle 'lignes' (forme brute VLM)"
            elif isinstance(bloc, dict):
                forme = 'dict row_code -> colonnes (tableau fixe)'
            else:
                forme = 'INATTENDUE : ' + _type_court(bloc)
            formes.setdefault(forme, []).append(
                str(p.get('page_id')) + '/' + tab)
    for forme, ou in sorted(formes.items()):
        print('  ' + forme)
        print('     ' + ', '.join(ou[:10])
              + (' ...' if len(ou) > 10 else ''))

    # ── ETAPE 4 : lecture unifiee ───────────────────────────────────────
    _titre('ETAPE 4 — Postes lus par lire_bloc')

    def lire_bloc(bloc):
        if isinstance(bloc, list):
            return [('ligne_' + str(i).zfill(3),
                     {k: v for k, v in row.items() if k != 'libelle_imprime'},
                     row.get('libelle_imprime'))
                    for i, row in enumerate(bloc) if isinstance(row, dict)]
        if isinstance(bloc, dict):
            if isinstance(bloc.get('lignes'), list):
                out = []
                for i, lg in enumerate(bloc['lignes']):
                    if isinstance(lg, dict):
                        out.append((lg.get('row_code') or 'ligne_' + str(i).zfill(3),
                                    lg.get('valeurs') or {},
                                    lg.get('libelle_imprime')))
                return out
            return [(rc, v, None) for rc, v in bloc.items() if isinstance(v, dict)]
        return []

    total_postes = total_valeurs = 0
    par_tableau = {}
    exemples = {}
    for p in avec_donnees:
        for tab, bloc in (p.get('donnees') or {}).items():
            if tab in ('brut', 'AUTRE') or bloc in (None, {}, []):
                continue
            for cle, vals, _lib in lire_bloc(bloc):
                n = sum(1 for v in (vals or {}).values() if v is not None)
                total_postes += 1
                total_valeurs += n
                if n:
                    par_tableau[tab] = par_tableau.get(tab, 0) + n
                    exemples.setdefault(tab, (cle, vals))

    print('Postes lus                   : ' + str(total_postes))
    print('Valeurs non nulles           : ' + str(total_valeurs))
    print('Detail par tableau           : ' + (', '.join(
        k + '=' + str(v) for k, v in sorted(par_tableau.items())) or '(aucun)'))

    if not total_valeurs:
        print()
        print('>>> RUPTURE : les blocs existent mais toutes les valeurs sont nulles.')
        print('    L extraction VLM n a rien lu. Verifiez les prompts et la')
        print('    qualite des images (cellule 6 : PDF_ZOOM, deskew).')
        return

    print()
    print('Exemple de poste par tableau :')
    for tab, (cle, vals) in sorted(exemples.items())[:6]:
        apercu = {k: v for k, v in list(vals.items())[:4] if v is not None}
        print('  ' + tab + '.' + str(cle) + ' -> ' + str(apercu))

    # ── ETAPE 5 : correspondance avec le mapping Excel ──────────────────
    if mapping is None:
        print()
        print('(Etape 5 ignoree : mapping non fourni. Dans le notebook, '
              'appelez diagnostiquer(chemin, MAP_LIGNES).)')
        return

    _titre('ETAPE 5 — Correspondance avec le mapping Excel')
    reconnus = inconnus = 0
    manquants = {}
    for p in avec_donnees:
        for tab, bloc in (p.get('donnees') or {}).items():
            if tab in ('brut', 'AUTRE') or bloc in (None, {}, []):
                continue
            for cle, vals, _lib in lire_bloc(bloc):
                if not any(v is not None for v in (vals or {}).values()):
                    continue
                if str(cle).startswith('ligne_'):
                    continue
                if tab in mapping and cle in mapping[tab]:
                    reconnus += 1
                else:
                    inconnus += 1
                    manquants.setdefault(tab, set()).add(cle)

    print('row_code reconnus par le mapping : ' + str(reconnus))
    print('row_code inconnus                : ' + str(inconnus))
    if manquants:
        print()
        print('>>> Ces row_code portent des valeurs mais ne sont pas mappes :')
        for tab, codes in sorted(manquants.items()):
            connus = sorted(mapping.get(tab, {}).keys())
            print('  Tableau ' + tab + ' (' + str(len(codes)) + ' inconnus)')
            for c in sorted(codes)[:12]:
                print('     - ' + str(c))
            if tab not in mapping:
                print('     -> ce TABLEAU entier est absent de MAP_LIGNES.')
            elif connus:
                print('     mapping attend : ' + ', '.join(connus[:8]) + ' ...')
    if reconnus == 0:
        print()
        print('>>> RUPTURE : aucun row_code ne correspond au mapping.')
        print('    Les noms de postes du JSON different de ceux de MAP_LIGNES')
        print('    (cellule 15). Comparez la liste ci-dessus a SCHEMAS.')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    diagnostiquer(sys.argv[1])
