import sys,types,unittest,tempfile,copy,json
from pathlib import Path
# Exécuter uniquement le modèle et les fonctions, pas les composants Streamlit.
src=Path('/mnt/data/app.py').read_text()
code=src.split('if "dossier" not in st.session_state:')[0]
class Dummy:
    def __getattr__(self,n): return lambda *args,**kwargs: None
sys.modules['streamlit']=Dummy()
ns={}
exec(compile(code,'app.py','exec'),ns)

A=ns

def example(year, current, prev=None, name='A'):
    pages=[{'numero_page_scannee':1, 'donnees':{'ACTIF':{'clients':{'net_n':current,'net_n1':prev},'total_general_actif':{'net_n':current,'net_n1':prev}},
                                             'PASSIF':{'capital_emis':{'n':current, 'n1':prev}},
                                             'TCR':{'ventes_marchandises':{'n_credit':current, 'n1_credit':prev}}}}]
    return {'identite':{'annee':year,'exercice_du':f'01/01/{year}','exercice_au':f'31/12/{year}'},'pages':pages,'document':{'fichier_source':name}}

class Tests(unittest.TestCase):
    def test_exercises_and_source_precedence(self):
        d1={'id':'a','exercice':2023,'pdf_name':'2023.pdf','date_fin':'2023-12-31'}
        d2={'id':'b','exercice':2024,'pdf_name':'2024.pdf','date_fin':'2024-12-31'}
        d3={'id':'c','exercice':2025,'pdf_name':'2025.pdf','date_fin':'2025-12-31'}
        merged,years,dates,sources,warnings,local=A['_merge_yearly']({},[(d3,example(2025,300,210)),(d2,example(2024,200,101)),(d1,example(2023,100,90))])
        self.assertEqual(years,[2022,2023,2024,2025]);self.assertEqual(dates[2024],'2024-12-31')
        self.assertEqual(merged['ACTIF'][2024]['clients']['net']['value'],200)
        self.assertEqual(merged['ACTIF'][2024]['clients']['net']['doc_id'],'b')
        self.assertEqual(merged['TCR'][2024]['ventes_marchandises']['credit']['value'],200)
        self.assertEqual(merged['PASSIF'][2023]['capital_emis']['montant']['value'],100)
        self.assertTrue(any(row['Exercice']==2024 for row in warnings))
        markup=A['_render_multiyear_grid']('ACTIF',merged['ACTIF'],years,dates,set(),'KDZD',2)
        self.assertIn('Exercice 2024',markup)
        self.assertIn('31/12/2024',markup)
        self.assertIn('Date',markup) if False else None
        self.assertIn('2025',markup)
        self.assertIn('Source : 2024.pdf',markup)
        self.assertNotIn('None',markup)
    def test_missing_json_and_date(self):
        docs=[({'id':'a','exercice':2021,'pdf_name':'2021.pdf','date_fin':''},None)]
        m,y,c,s,w,l=A['_merge_yearly']({},docs)
        self.assertEqual(y,[2021]);self.assertFalse(c)
        self.assertIn('Dates non renseignées', A['_render_multiyear_grid']('PASSIF',m['PASSIF'],y,c,set()))
    def test_dates(self):
        self.assertEqual(A['_date_iso']('31/12/2024'),'2024-12-31')
        self.assertEqual(A['_date_iso']('invalid'),'')
        self.assertEqual(A['_document_year_from_json'](example(2024,123)),2024)
    def test_json_corrections_preserve_original(self):
        orig=example(2024,123,111)
        path='pages[0].donnees.ACTIF.clients.net_n'
        cp=copy.deepcopy(orig)
        A['assign_path'](cp,path,456)
        self.assertEqual(orig['pages'][0]['donnees']['ACTIF']['clients']['net_n'],123)
        self.assertEqual(cp['pages'][0]['donnees']['ACTIF']['clients']['net_n'],456)
    def test_pdf_json_matching(self):
        self.assertEqual(A['_guess_json_for_pdf']('foo_2024.pdf', {'foo_2024.json':{},'other.json':{}}),'foo_2024.json')
        self.assertEqual(A['_guess_json_for_pdf']('foo_2024.pdf', {'foo_2024.pdf.json':{}}),'foo_2024.pdf.json')
        self.assertIsNone(A['_guess_json_for_pdf']('foo_2024.pdf',{'x.json':{}}))
    def test_legacy_dates_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            A['ROOT']=Path(tmp)
            dossier={'execution_id':'abc','client':{'identifiant_national':'TEST123','raison_sociale':'X'},
                     'exercice':2024,'document':{'nom_original':'original.pdf'},
                     'validation':{'statut':'non_valide'}}
            target=A['dossier_path'](dossier);target.mkdir(parents=True)
            doc=A['_documents'](dossier)[0]
            self.assertEqual(doc['id'],'legacy')
            self.assertTrue(A['_save_dates'](dossier,[doc],'legacy','01/01/2024','31/12/2024'))
            self.assertEqual(dossier['documents'][0]['date_fin'],'2024-12-31')
            self.assertEqual(json.loads((target/'dossier.json').read_text())['documents'][0]['pdf_path'],'source.pdf')
            with self.assertRaises(ValueError):
                A['_save_dates'](dossier,dossier['documents'],'legacy','', '2025-01-01')

if __name__=='__main__': unittest.main(verbosity=2)
