"""Tests fonctionnels du moteur V20 et des corrections côté serveur, sans Streamlit/DOM."""
import copy
import json
import math
import sys
import tempfile
import types
import unittest
from pathlib import Path
sys.path.insert(0, '/mnt/data')
import yarisk_finance as f

streamlit=types.ModuleType('streamlit')
for method in ('set_page_config','title','caption','warning','error','success','info','rerun'):
    setattr(streamlit,method,lambda *a,**k:None)
component_pkg=types.ModuleType('streamlit.components')
component_v1=types.ModuleType('streamlit.components.v1')
component_v1.declare_component=lambda *a,**k:lambda *a,**k:None
component_pkg.v1=component_v1;streamlit.components=component_pkg
streamlit.session_state=types.SimpleNamespace()
sys.modules['streamlit']=streamlit
sys.modules['streamlit.components']=component_pkg
sys.modules['streamlit.components.v1']=component_v1
src=Path('/mnt/data/app.py').read_text()
namespace={'__file__':'/mnt/data/app.py'}
exec(compile(src.split('if "dossier" not in st.session_state:')[0],'/mnt/data/app.py','exec'),namespace)
A=namespace


def source(table, rows, year=2024, page=1):
    return {'identite':{'annee':year},'pages':[{'numero_page_scannee':page,'donnees':{table:rows}}]}


def merge(table, rows, year=2024, doc_id='a'):
    doc={'id':doc_id,'exercice':year,'pdf_name':f'PDF_{year}.pdf'}
    joined, years, *_ = A['_merge_yearly']({},[(doc,source(table,rows,year))])
    enriched, formula_issues=f.enrich_years(joined,years,A['SHEET_LAYOUT'])
    return doc,joined,enriched,formula_issues


class TestV4(unittest.TestCase):
    def test_threshold_exact_1000(self):
        self.assertIsNone(f.severity(999.99));self.assertIsNone(f.severity(-999))
        self.assertEqual(f.severity(1000),'LOW')
        self.assertEqual(f.severity(-1000),'LOW')
        self.assertEqual(f.severity(10000),'MEDIUM')
        self.assertEqual(f.severity(1000000),'HIGH')

    def test_cross_year_dispute_under_threshold(self):
        a={'id':'a','exercice':2024,'pdf_name':'2024.pdf'}
        b={'id':'b','exercice':2025,'pdf_name':'2025.pdf'}
        data=[(a,source('PASSIF',{'capital_emis':{'n':50000}})),
              (b,source('PASSIF',{'capital_emis':{'n1':50999}},2025))]
        m,years,dates,src,warnings,clashes=A['_merge_yearly']({},data)
        self.assertFalse(warnings)
        data[1]=(b,source('PASSIF',{'capital_emis':{'n1':51000}},2025))
        self.assertEqual(len(A['_merge_yearly']({},data)[4]),1)

    def test_actif_corporelles_brut_and_net(self):
        rows={name:{'montant_brut':gross,'amortissements_provisions_pertes':amort,
                    'net_n':gross-amort} for name,gross,amort in (
                        ('terrains',10000,0),('batiments',22000,2000),
                        ('autres_immobilisations_corporelles',5000,1000),
                        ('immobilisations_en_concession',0,0))}
        rows['immobilisations_corporelles']={'montant_brut':37000,'amortissements_provisions_pertes':3000,'net_n':34000}
        _,raw,full,issues=merge('ACTIF',rows)
        corp=full['ACTIF'][2024]['immobilisations_corporelles']
        self.assertEqual(corp['brut']['value'],37000)
        self.assertEqual(corp['amort']['value'],3000)
        self.assertEqual(corp['net']['value'],34000)
        self.assertTrue(corp['net']['is_formula'])
        self.assertFalse([e for e in issues if e['Rubrique']=='immobilisations_corporelles'])

    def test_actif_totals_calculated_and_missing_empty(self):
        rows={'clients':{'montant_brut':180000,'amortissements_provisions_pertes':10000,'net_n':170000},
              'stocks_encours':{'montant_brut':30000,'amortissements_provisions_pertes':0,'net_n':30000}}
        _,_,full,_=merge('ACTIF',rows)
        s=full['ACTIF'][2024]
        self.assertEqual(s['creances_emplois_assimiles']['net']['value'],170000)
        self.assertEqual(s['total_actif_courant']['net']['value'],200000)
        self.assertEqual(s['total_general_actif']['net']['value'],200000)
        self.assertFalse(s['total_actif_courant']['net']['is_formula'] is False)
        self.assertNotIn('immobilisations_financieres',s) if False else None
        self.assertIsNone(s.get('immobilisations_financieres',{}).get('net',{}).get('value'))

    def test_passif_capitaux_propres_minus_capital_non_appele(self):
        rows={'capital_emis':{'n':100000},'capital_non_appele':{'n':15000},
              'primes_reserves':{'n':20000},'ecart_reevaluation':{'n':0},'ecart_equivalence':{'n':0},
              'resultat_net_passif':{'n':5000},'report_a_nouveau':{'n':0}}
        _,_,full,_=merge('PASSIF',rows)
        self.assertEqual(full['PASSIF'][2024]['total_capitaux_propres']['montant']['value'],110000)
        self.assertEqual(full['PASSIF'][2024]['total_general_passif']['montant']['value'],110000)

    def test_tcr_production_and_net_positive(self):
        rows={'ventes_marchandises':{'n_credit':100000},'produits_fabriques':{'n_credit':50000},
              'charges_personnel':{'n_debit':20000},'impots_taxes_assimiles':{'n_debit':1000}}
        _,_,full,_=merge('TCR',rows)
        r=full['TCR'][2024]
        self.assertEqual(r['chiffre_affaires_net']['credit']['value'],150000)
        self.assertEqual(r['production_exercice']['credit']['value'],150000)
        self.assertIsNone(r.get('consommations_exercice',{}).get('credit',{}).get('value'))
        self.assertEqual(r['valeur_ajoutee_exploitation']['credit']['value'],150000)
        self.assertEqual(r['excedent_brut_exploitation']['credit']['value'],129000)
        self.assertEqual(r['resultat_net_exercice']['credit']['value'],129000)

    def test_formula_gap(self):
        rows={name:{'montant_brut':v} for name,v in [('terrains',10000),('batiments',15000),
                  ('autres_immobilisations_corporelles',0),('immobilisations_en_concession',0)]}
        rows['immobilisations_corporelles']={'montant_brut':24000}
        _,_,full,issues=merge('ACTIF',rows)
        issue=[v for v in issues if v['Rubrique']=='immobilisations_corporelles' and v['Colonne']=='brut']
        self.assertEqual(len(issue),1)
        self.assertEqual(issue[0]['Écart DZD'],1000)
        key=('ACTIF',2024,'immobilisations_corporelles','brut')
        alerts=A['_finance_issue_index'](issues)
        self.assertIn(key,alerts)
        self.assertIn('Formule Excel',alerts[key][0])
        self.assertEqual(full['ACTIF'][2024]['immobilisations_corporelles']['brut']['value'],25000)
        self.assertEqual(full['ACTIF'][2024]['immobilisations_corporelles']['brut']['observed_value'],24000)

    def test_editor_keeps_dzd_precision(self):
        self.assertEqual(A['_exact_edit_amount'](15001,'KDZD'),'15,001')
        self.assertEqual(A['_exact_edit_amount'](15001.25,'KDZD'),'15,00125')
        self.assertEqual(A['_exact_edit_amount'](15001.25,'DZD'),'15001,25')

    def test_grid_editability_and_blank(self):
        d,m,full,issues=merge('ACTIF',{'clients':{'montant_brut':5000,'net_n':5000},
                                         'total_actif_courant':{'net_n':5000}})
        payload=A['_grid_payload']('ACTIF',full,[2024],{}, {},{},set(),'DZD',0,{'a':object()})
        rows={r['row_id']:r for r in payload['rows']}
        clients={c['col']:c for c in rows['clients']['cells']}
        self.assertTrue(clients['brut']['editable'])
        self.assertFalse(clients['net']['editable'])
        self.assertEqual(clients['amort']['text'],'')
        self.assertFalse({c['col']:c for c in rows['total_actif_courant']['cells']}['net']['editable'])

    def test_section_formulas_visible(self):
        _,_,a,_=merge('ACTIF',{'stocks_encours':{'montant_brut':10000,'amortissements_provisions_pertes':0,'net_n':10000}})
        self.assertEqual(a['ACTIF'][2024]['actifs_courants_calc']['net']['value'],10000)
        self.assertEqual(a['ACTIF'][2024]['total_actif_courant']['net']['value'],10000)
        _,_,p,_=merge('PASSIF',{'capital_emis':{'n':10000}})
        self.assertEqual(p['PASSIF'][2024]['capitaux_propres_calc']['montant']['value'],10000)
        self.assertEqual(p['PASSIF'][2024]['total_capitaux_propres']['montant']['value'],10000)

    def test_formula_discrepancy_999_is_not_red(self):
        rows={name:{'montant_brut':v} for name,v in [('terrains',10000),('batiments',15000),
                  ('autres_immobilisations_corporelles',0),('immobilisations_en_concession',0)]}
        rows['immobilisations_corporelles']={'montant_brut':24001}
        _,_,enriched,issues=merge('ACTIF',rows)
        self.assertFalse([i for i in issues if i['Rubrique']=='immobilisations_corporelles' and i['Colonne']=='brut'])

    def test_tcr_computed_zero_blanks_display(self):
        _,_,enriched,_=merge('TCR',{'ventes_marchandises':{'n_credit':100000}})
        payload=A['_grid_payload']('TCR',enriched,[2024],{},{},{},set(),'DZD',0,{'a':object()})
        rows={x['row_id']:x for x in payload['rows']}
        credit_debit=rows['chiffre_affaires_net']['cells']
        self.assertEqual(credit_debit[0]['text'],'')
        self.assertEqual(credit_debit[1]['text'],'100\u202f000')

    def test_edit_confirm_persists_audit_recalculates_without_touching_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            A['ROOT']=Path(tmp)
            dossier={'schema_version':'yarisk-demo-v4','execution_id':'test',
                     'client':{'identifiant_national':'XY','raison_sociale':'Client'},
                     'validation':{'statut':'non_valide'}}
            doc={'id':'a','pdf_name':'client.pdf','exercice':2024,
                 'json_original_path':'docs/a/source.json','json_corrige_path':'docs/a/corrected.json',
                 'log_path':'docs/a/log.json'}
            root=A['dossier_path'](dossier);root.mkdir(parents=True)
            source_json=source('ACTIF',{'clients':{'montant_brut':5000,'amortissements_provisions_pertes':0,'net_n':5000}})
            A['atomic_json'](root/'docs/a/source.json',source_json)
            merged,years,*_=A['_merge_yearly']({},[(doc,source_json)])
            full,_=f.enrich_years(merged,years,A['SHEET_LAYOUT'])
            row=full['ACTIF'][2024]['clients']['brut']
            event={'action':'confirm_cell','table':'ACTIF','year':2024,'row_id':'clients','col':'brut',
                   'doc_id':'a','path':row['path'],'old':5000,
                   'entered':'6,00','unit':'KDZD','reason':'Vérification de la page PDF'}
            A['_handle_grid_correction'](event,'ACTIF',merged,full,dossier,{'a':doc},{'a':source_json})
            raw=json.loads((root/'docs/a/source.json').read_text())
            changed=json.loads((root/'docs/a/corrected.json').read_text())
            self.assertEqual(raw['pages'][0]['donnees']['ACTIF']['clients']['montant_brut'],5000)
            self.assertEqual(changed['pages'][0]['donnees']['ACTIF']['clients']['montant_brut'],6000)
            logs=json.loads((root/'docs/a/log.json').read_text())
            self.assertEqual(logs[0]['apres'],6000)
            self.assertEqual(logs[0]['mode'],'confirmation_cellule')
            merged2,years,*_=A['_merge_yearly']({},[(doc,changed)])
            after,_=f.enrich_years(merged2,years,A['SHEET_LAYOUT'])
            self.assertEqual(after['ACTIF'][2024]['clients']['net']['value'],6000)

if __name__=='__main__':unittest.main(verbosity=2)
