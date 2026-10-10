# YaRisk V4 — Validation financière interactive (pilote Domino)

## Changements par rapport à V3.1

**1. Seuil de signalement : 1 000 DZD inclus.** Ce seuil s'applique aux *écarts de montant* entre documents, aux divergences internes de pages et aux comparaisons entre montant calculé depuis Excel V20 et montant observé dans le JSON. Les seuils du notebook V29d sont repris : 1 000 (LOW), 10 000 (MEDIUM), 1 000 000 DZD (HIGH). Un écart de 999 DZD n'est pas signalé. Les incohérences de dates peuvent être listées indépendamment, car elles ne sont pas des écarts monétaires.

**2. Formules réellement calculées.** Le registre `v20_financial_formulas.json` est constitué par lecture du classeur officiel `MODEL ETAT FINANCIER - ANALYSTE COPILOTE V20.xlsx`, feuilles « Saisie actif », « Saisie passif » et « Saisie TCR ». Il comporte 46 formules ACTIF, 7 PASSIF et 20 TCR pour une année-type. Il inclut les totaux et regroupements : immobilisations corporelles, immobilisations financières, créances, disponibilités, actifs non courants/courants, total général, capitaux propres, passifs courants/non courants, résultat net et agrégats TCR. Les lignes-titres ACTIF et PASSIF qui portaient une formule mais n'avaient pas d'identifiant dans V3 sont maintenant calculées.

L'évaluation est **locale en Python**, sans appel Excel ou LibreOffice sur Domino. Les formules originales sont appliquées à chacune des années, pour lesquelles des données ont été importées. Les valeurs JSON sont supposées en **DZD** comme dans V29d, les colonnes ACTIF/PASSIF du classeur V20 en **KDZD**, le TCR du classeur V20 en **DZD**. Une cellule calculée à partir de composantes incomplètes est signalée comme « calcul potentiellement incomplet » dans son info-bulle et ne déclenche pas une anomalie de formule certifiée. La V4 ne remplace **jamais** la valeur extraite d'origine : elle conserve `observed_value` distinct de `calculated_value` dans la vue.

**3. Correction dans la grille.** Dans ACTIF / PASSIF / TCR, **cliquer** sur une cellule de saisie (non-formule) qui possède un chemin JSON modifiable. Saisir le montant corrigé dans l'unité d'affichage, préciser une justification, puis cliquer sur « Confirmer la correction ». La valeur source est enregistrée en DZD dans `extraction_corrigee.json` ; `extraction_originale.json` reste intact. Une entrée horodatée est ajoutée à l'historique du PDF (`corrections.json`). La validation du dossier est remise à « non_valide ». Les formules sont recalculées automatiquement au rechargement. Les cellules portant des formules V20 sont verrouillées. La valeur saisie n'est pas arrondie dans l'éditeur, même quand le tableau affiche moins de décimales.

**4. Lisibilité.** Palette issue des styles du fichier Excel V20 : #00915A, #00573F, #C6E5D4, #EAF5EF, #FFF8E1. L'anomalie `>=1000 DZD` colore la *police* de la cellule en rouge, avec une info-bulle indiquant la règle, les valeurs, l'écart, les PDF, les pages disponibles et l'action de vérification. Les cellules sans donnée restent vides ; les zéros techniques des branches TCR non utilisées restent invisibles.

## Déploiement sur Domino

**Important : ne pas remplacer uniquement `app.py`.** La V4 dépend des nouveaux fichiers `yarisk_finance.py`, `v20_financial_formulas.json` et du dossier `yarisk_grid/`.

À la racine du projet Domino, disposer :

```
app.py
app.sh
requirements.txt
yarisk_finance.py
v20_financial_formulas.json
yarisk_grid/
  index.html
```

1. Décompresser le package V4 complet dans le projet Domino privé, à la même racine que l'ancien `app.py`.
2. Conserver vos répertoires de données et liasses existants (ne pas supprimer le répertoire pointé par `YARISK_DATA_DIR`).
3. Veiller à ce que l'environnement Domino installe `streamlit>=1.32,<2` depuis `requirements.txt` et soit compatible avec le proxy Streamlit / iframe des custom components.
4. Lancer `./app.sh` (port Domino configuré via `PORT`, défaut 8888).
5. Importer une liasse PDF et son JSON, ouvrir **3 · Bilan pluriannuel**, vérifier les calculs puis tester la correction d'une cellule de saisie avec un motif.

Le registre de formules est intégré au package, donc le `.xlsx` original et le notebook V29d ne sont **pas requis pendant le fonctionnement** de la grille. Ils restent les références métier et doivent être conservés séparément. L'application n'exécute toujours **pas** le notebook : PDF → JSON reste une opération externe dans cette démo.

## Vérifications

- `python test_v4.py` : tests du seuil, des formules ACTIF/PASSIF/TCR, des lignes-titres calculées, de la correction avec trace et non-écrasement de l'original, du rendu vide et de la conversion des unités.
- `python -m py_compile app.py yarisk_finance.py` : validation syntaxique Python.
- Le JavaScript du composant a été vérifié syntaxiquement. **L'affichage et l'édition de bout en bout sur Domino doivent encore être validés dans votre environnement** ; les tests locaux n'équivalent pas à cette validation.

## Limites de sécurité et métier

Version **mono-opérateur de démonstration**, sans authentification métier ni séparation multi-utilisateurs. Ne pas charger des données bancaires de production sans autorisation DSI et volume sécurisé persistant. Les contrôles additionnels V29d, notamment la certification de la liasse, la validation métier définitive et l'export Excel V20, restent à intégrer. Les calculs dont des composantes sont absentes peuvent être partiels : ils ne doivent pas être utilisés seuls pour certifier un bilan.
