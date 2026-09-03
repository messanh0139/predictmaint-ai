# Données brutes — jeu de données FD001

Fichiers utilisés :

- `train_FD001.txt`
- `test_FD001.txt`
- `RUL_FD001.txt`

Le fichier `readme.txt` d'origine est conservé à côté des données.

Les empreintes SHA256 sont recalculées à chaque exécution de `python -m src.data.prepare` et enregistrées dans `data/processed/split_manifest.json`, puis propagées dans `models/model_metadata.json` afin de lier un modèle à la version exacte des données.

Ne pas modifier manuellement les fichiers bruts. Toute transformation doit être reproduite par le code du projet.
