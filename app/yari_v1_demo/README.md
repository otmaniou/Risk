# Ya-Risk V1 — pilote Domino

## Démarrage

1. Importer le dossier dans un projet Domino privé.
2. Installer `requirements.txt` dans le Compute Environment de l'application.
3. Configurer `YARISK_DATA_DIR` vers un stockage **persistant et approuvé** monté en lecture-écriture. Sans cela, `./data` est seulement temporaire.
4. Publier une Domino App avec la commande `./app.sh`. Vérifier le port et le proxy avec l'administrateur Domino.
5. Saisir la fiche client, importer un PDF et, si disponible, un JSON produit par le notebook V29d.
6. Consulter le JSON, modifier une valeur avec justification, et vérifier les fichiers sauvegardés dans l'onglet Archive.

## Limitations explicites

- Le notebook V29d est fourni **inchangé** dans `reference/`. Il n'est pas exécuté par l'application. Son chargement vLLM/GPU et son flux PDF→JSON restent à intégrer et tester sur Domino.
- Le modèle Excel V20 est fourni **inchangé** dans `templates/`. L'export n'est pas encore activé : il ne doit être disponible qu'après intégration des contrôles et validation métier.
- L'affichage JSON est générique et ne constitue pas encore une interface spécialisée ACTIF/PASSIF/TCR.
- L'archive n'est pas une base SQL transactionnelle. Usage **mono-opérateur** uniquement.
- Ne pas utiliser de données bancaires réelles avant validation DSI (stockage, sauvegardes, accès, chiffrement, durée de conservation).
- Les corrections de JSON importé ne sont pas automatiquement répercutées sur les calculs du notebook ; la validation reste désactivée.

## Organisation

`app.py` interface, `app.sh` démarrage, `requirements.txt` dépendances, `reference/` notebook V29d, `templates/` modèle Excel V20.
