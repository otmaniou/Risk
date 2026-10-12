# Ya-Risk — POC de bout en bout

PDF des liasses → extraction Qwen (moteur V29d) → Bilan Actif / Passif / TCR (corrections avec recalcul en direct) → validation → Excel ANALYSTE V20.

## Contenu

| Fichier | Rôle |
|---|---|
| `app.py`, `app.sh`, `requirements.txt` | Interface web Streamlit (parcours guidé en 5 étapes) |
| `bilan_view.py` | Schéma Actif/Passif/TCR, formules V20, consolidation multi-exercices, contrôles |
| `bilan_grid/` | Grille de type Excel (saisie, recalcul pendant la frappe, anomalies) |
| `bilan_grid/wb_engine.js` | Moteur de formules Excel dans le navigateur (feuilles Saisie et Etatsfin) |
| `bilan_grid/model_saisie.js` | Formules, styles et cellules de saisie du modèle ANALYSTE V20 (généré) |
| `saisie_model.py` | Saisies analyste Saisie / Etatsfin, écritures reportées dans l'Excel |
| `tools/build_saisie_model.py` | Régénère `model_saisie.js` et `crf_template.xlsx` si un modèle Excel change |
| `tools/crf_mapping.py` | Correspondance rubriques CRF ↔ liasse (Actif / Passif / TCR), modifiable |
| `bilan_grid/crf_template.xlsx` | Feuilles CRF préparées (ajoutées par le worker à l'Excel généré) |
| `notebook/cellule_19_worker_yarisk.py` | Cellule à coller à la fin du notebook V29d : le « worker » GPU |

## 1. Un répertoire partagé

L'appli et le notebook doivent voir **le même dossier**. Sur Domino : le Dataset `/domino/datasets/local/YaRisk/yarisk_app`
(fixé par `app.sh` et par la cellule 0 du notebook).

## 2. Notebook V29d (GPU) : le moteur

1. Ajouter en tout début de notebook une **cellule 0** :

```python
import os
os.environ["YARISK_APP_ROOT"]   = "/domino/datasets/local/YaRisk/yarisk_app"        # dossier partagé avec l'appli
os.environ["YARISK_INPUT_DIR"]  = "/domino/datasets/local/YaRisk/yarisk_app/_vide"  # vide : aucun traitement « batch »
os.environ["YARISK_OUTPUT_DIR"] = "/domino/datasets/local/YaRisk/yarisk_app/_v29d"  # sorties techniques V29d
os.makedirs(os.environ["YARISK_INPUT_DIR"], exist_ok=True)
```

2. Exécuter les cellules 1 à 17 (chargement de Qwen et des fonctions ; les boucles batch ne trouvent rien à traiter).
3. Coller puis exécuter `cellule_19_worker_yarisk.py` en dernière cellule. Elle tourne en continu et affiche
   « Worker Ya-Risk démarré ». Pour l'arrêter, utiliser le bouton **Interrupt**.

Le worker reprend **la logique de la cellule 11 sans modification** (classification, lecture ACTIF/PASSIF/TCR,
double lecture TCR, identité, contrôles). Il publie sa progression, puis génère l'Excel V20 avec `build_client_excel`
(cellule 16, recalcul LibreOffice) une fois le bilan validé.

## 3. Interface web

```bash
./app.sh        # YARISK_DATA_DIR=/domino/datasets/local/YaRisk/yarisk_app, port 8888
```

Parcours : **Dossier** (fiche client et 1 à 5 PDF) → **Extraction** (progression en direct, puis ouverture automatique
du bilan) → **Bilan** (grille, corrections avec motif) → **Validation** (commentaire obligatoire s'il reste une anomalie
HIGH) → **Excel V20** (généré automatiquement, à télécharger).

Dans la barre latérale, le voyant « Moteur Qwen » est vert quand la cellule worker tourne. Pour une démonstration
sans GPU, utiliser **Mode démonstration** à l'étape 1 et importer des JSON V29d.

### Contrôle visuel avec la liasse PDF

Dans le Bilan, le bouton **📄 Liasse PDF** affiche la page de la liasse à droite du tableau. Avec « Suivre la
sélection », la page suit la cellule choisie : bonne liasse, bonne page (TCR partie 1 ou 2) et colonne à lire (N ou N-1).
Les images sont produites par le worker lors de l'extraction (PyMuPDF du notebook), donc l'appli n'a rien à installer.
Les dossiers importés en JSON sans PDF n'ont pas d'aperçu.

### Feuilles Saisie et Etatsfin

Les onglets **Saisie** et **Etatsfin** reproduisent les feuilles du modèle ANALYSTE V20 (KDZD, mêmes couleurs et formats).
Elles sont calculées dans le navigateur avec **les formules exactes du classeur** (`wb_engine.js`), à partir des onglets
Actif / Passif / TCR : une correction de liasse ou une saisie se répercute immédiatement dans Saisie puis dans Etatsfin
(bilan fonctionnel, compte de résultat, tableau de flux, ratios).

- Cellules **bleues** = saisies analyste (annexes, hors bilan, crédit-bail, cessions, échéancier de la dette…), enregistrées
  dans `saisie.json` par exercice. Commentaire facultatif.
- Préparation du modèle, identique à l'écran et dans l'Excel : les valeurs d'exemple du modèle (autre société) sont vidées ;
  chaque ligne reprend pour tous les exercices la formule de la colonne N, décalée vers l'exercice (le modèle d'origine ne
  reliait que la colonne N) ; 8 cellules cassées (#REF!, liens externes) sont réparées d'après leur ligne. Restent cassées,
  sans effet à l'écran : Saisie passif lignes 29-30 (lien externe) et la colonne grise N de Saisie.
- À la validation, l'appli écrit `validation/saisie_excel.json` ; le worker l'applique à l'Excel généré puis recalcule.
- Si le modèle Excel change : `python tools/build_saisie_model.py "MODELE.xlsx"` régénère `bilan_grid/model_saisie.js`.

### Feuilles CRF (BNP Paribas Credit Rating Framework)

L'onglet **CRF** reprend les 7 feuilles du classeur CRF (Bilan actifs, Bilan passifs, Compte de résultat, Flux de trésorerie,
Ratios & agrégats, Leveraged / BCE, Rolling CF), en **Million DZD**, colonnes N / N-1 / N-2, avec toutes leurs formules.
63 rubriques sont reprises automatiquement de la liasse (fond vert) ; la liste et le niveau de confiance sont dans le
sous-onglet « Correspondance liasse » et dans `tools/crf_mapping.py`. Une valeur saisie sur une rubrique reprise la remplace
(coin orange), Suppr revient à la liasse. Contrôles : total actif CRF = total passif, résultat net CRF = résultat au passif,
réconciliation du flux de trésorerie. Les feuilles CRF sont ajoutées à l'Excel généré.
Régénération : `python tools/build_saisie_model.py "MODELE_V20.xlsx" "CRF.xlsx"`.

## Données d'un dossier

```
dossiers/<NIF>/<horodatage>/
  dossier.json          fiche client, statut, validation
  pdf/                  liasses déposées
  statut.json           progression de l'extraction (écrit par le worker)
  extractions/          JSON V29d originaux (jamais modifiés)
  apercu/<liasse>/      images JPEG des pages Actif / Passif / TCR (vue « Liasse PDF »)
  travail/              JSON corrigés (mis à jour à chaque enregistrement)
  corrections.json      historique : cellule, liasse, avant, après, motif, date
  saisie.json           saisies analyste des feuilles Saisie / Etatsfin (KDZD, par exercice)
  validation/           JSON validés figés + bilan_valide.json + saisie_excel.json + Excel V20
  excel_job.json        génération Excel (écrit par le worker)
```

## Règles multi-exercices

- Pour chaque exercice et chaque état, la **colonne N de la liasse de l'année** est retenue. À défaut, c'est la
  **colonne N-1 de la liasse suivante** (règle `choose_candidates` du V29d). Au plus 5 exercices sont affichés.
- Lorsque les deux existent, la colonne N-1 de la liasse suivante sert de **contrôle inter-liasses** (écart ≥ 1 000 DZD signalé).
- Pour un exercice lu uniquement en N-1, l'Actif ne donne que le Net : les colonnes Brut et Amortissements sont
  hachurées et non modifiables.

## Limites du POC

Un seul utilisateur, sans authentification. Un dossier est traité à la fois. Le notebook doit rester ouvert pendant
la démonstration. Les ratios web sont calculés depuis la liasse seule (sans retraitements analyste du classeur V20).
