# RoadToTrading — Job Intelligence (Buy-side / Quant / Market trading, Europe)

Système de **couverture du marché de l'emploi** trading / quant / structuring /
strats en Europe (Paris · Londres · Genève prioritaires). Ce n'est pas un job
board : l'objectif est de **capturer en continu** les offres pertinentes des
desks buy-side, market makers, prop shops et banques (markets only), de les
**normaliser, dédupliquer et historiser**, et de garantir une **couverture
mesurée** (≈95 % sur la watchlist ATS) — pas une garantie absolue de zéro-manqué
(intenable sur sources fermées).

## Contraintes assumées (décisions actées)

| Sujet | Décision |
|---|---|
| Budget | **0 €** hors Claude Pro → pas de proxy/LLM payant runtime, pas de VPS |
| Compute | **GitHub Actions** cron 2×/jour (gratuit) |
| Stockage | **JSON git-diffable** committé dans le repo (historique = git, 0 binaire) |
| Frontend | **SPA statique** sur GitHub Pages, filtrage client-side |
| Sources socle | **Career pages via ATS** (Greenhouse/Lever/Ashby/Recruitee/Workable/SmartRecruiters) |
| LinkedIn / eFC | **best-effort** seulement (anti-bot + légal ⇒ non garanti à 0 €) |
| « IA » | **règles déterministes** (taxonomie) ; LLM = humain/Claude en maintenance |
| Périmètre | Trading, Quant Trading, Quant Research, Structuring, Strats, Quant Dev (2ndaire) — **pas de Sales**, pas d'AM long-only / risk / compliance / ops / M&A |
| « 1 offre » | même req multi-villes = **1 offre** (union des localisations) |

## Architecture

```
GitHub Actions (cron 2x/jour)
   │
   ├─ scrapers ATS (JSON officiels, isolés par employeur)
   │     greenhouse · lever · ashby · recruitee · workable · smartrecruiters
   │
   ├─ pipeline (déterministe, 0 LLM)
   │     normalize → classify (rôle/scope/séniorité/asset) → dedup multi-sources
   │     → diff vs run précédent (NEW / MODIFIED / CLOSED)
   │
   ├─ état canonique  → data/state/*.json   (committé, diffable)
   │     changelog    → data/changelog.ndjson
   │
   └─ export          → web/data/*.json      → SPA statique (GitHub Pages)
```

## Modèle de données

Trois couches (voir `jobintel/models.py`) :

- **RawPosting** — une annonce brute d'une source (avant traitement).
- **JobSource** — annonce normalisée et persistée. Relation **1 Job ↔ N sources**
  (une offre vue sur Greenhouse *et* LinkedIn = 2 sources, 1 job).
- **Job** — l'offre **canonique** affichée, dédupliquée, multi-villes.

Clé canonique : `sha1(employer_id | titre_normalisé | role_family)`. Les annonces
d'un même intitulé chez un même employeur fusionnent ; leurs villes sont
**unionnées** (décision « 1 offre multi-villes »). Les annonces de recruteurs
anonymisées ne sont **pas** fuzzy-linkées (évite les fausses fusions).

### Détection de changements
- `content_hash` = hash(titre normalisé + villes + rôle + séniorité + sources).
- `NEW` : job_id inédit. `MODIFIED` : content_hash changé (nouvelle ville,
  nouvelle source, reclassification…). `CLOSED` : absent ≥ `GRACE_RUNS` (2)
  runs consécutifs — **uniquement** si la source a été crawlée avec succès
  (un scraper en échec ne ferme jamais d'offres). Rétention : purge des
  fermées > 180 j.

### Classification (déterministe)
`config/taxonomy.yaml` pilote tout : exclusions dures d'abord, puis scoring des
familles **pondéré par spécificité** (« quantitative trader » > « trader »), avec
les titres d'ingénierie routés vers `QUANT_DEV` uniquement (anti-bruit dans la
vue Trading prioritaire). Sortie : `role_family`, `in_scope` + raison,
`seniority`, `asset_classes`.

## Watchlist & détection d'ATS

`config/employers.yaml` — chaque employeur a un `status` :
- `verified` : endpoint sondé en direct, renvoie les vraies offres de la firme.
- `candidate` : firme cible dont l'ATS est custom/Workday/non résolu.

`python -m scripts.detect_ats` sonde les candidats sur tous les providers et
**n'accepte un token que s'il renvoie ≥ 1 vraie offre** (garde-fou contre les
faux positifs Workable/SmartRecruiters qui répondent 200 sur un compte vide).
Résultats → `data/ats_detection.json`, à valider puis reporter dans le YAML.

## Frontend

`web/` (statique) — 3 vues : **Offres** (recherche + filtres rôle/type/séniorité/
asset/source/ville-cible/statut, vue consolidée + liens sources), **Activité**
(flux NEW/MODIFIED/CLOSED), **Sources** (santé par employeur, « muette depuis N
runs »). Aucune compilation, aucun backend.

## Lancer en local

```bash
pip install -r requirements.txt
python -m scripts.run_crawl       # crawl + export web/data
python -m scripts.detect_ats      # (optionnel) résoudre les ATS inconnus
python -m http.server -d web 8000 # ouvrir http://localhost:8000
```

## Risques & limites (explicites)

- **Couverture ≠ exhaustivité.** Sources fermées (LinkedIn/eFC), recrutement par
  réseau et firmes sans career page publique ⇒ des offres seront manquées. SLA =
  couverture **mesurée** sur la watchlist, pas garantie absolue.
- **Banques & Workday/custom** : non couverts par les scrapers ATS JSON ⇒
  `candidate`, en attente de scrapers dédiés ou fallback agrégé.
- **Fragilité ATS** : si un provider change son schéma, le scraper concerné casse
  — isolé (n'impacte pas les autres) et signalé via la santé des sources.
- **Dédup** : deux reqs distinctes au même intitulé/employeur fusionnent
  (trade-off assumé ; les sources restent listées individuellement).
- **Classification** : règles, pas LLM ⇒ quelques bords mal rangés. Un passage
  LLM optionnel peut être ajouté sans changer le schéma.

## Maintenance long terme

- Surveiller l'onglet **Sources** / les warns `SOURCES MUTE` du crawl.
- Étendre la watchlist via `detect_ats` (objectif régime ~300 employeurs).
- Ajouter un scraper = une classe dans `jobintel/scrapers/` + entrée registry.
- Ajuster la taxonomie dans `config/taxonomy.yaml` (aucun code à toucher).
