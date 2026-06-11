# Environnements (test/prod) & domaine définitif — plan de déploiement

> **Nature de ce document.** Plan d'infra que tu possèdes et édites, lié au roll-out
> de Cohérence (cf. `docs/strategy/FORECAST.md` §7 et la spec 9.10 « monitoring du
> trafic / events » en cours d'écriture). Il fixe deux décisions structurantes :
> (1) un **environnement de test isolé de la prod**, (2) le **domaine définitif** et
> l'hébergement. Les valeurs non sourcées sont marquées `[HYPOTHÈSE]`.
>
> **Dernière mise à jour** : 2026-06-11.
>
> **STATUT : LIVRÉ EN PRODUCTION (2026-06-11).** Prod et staging tournent chacun
> sur leurs sous-domaines `coherence-metz.fr`, totalement isolés. Détail des URL
> et des actions réalisées en §5.3 et §8.

---

## 0. Décisions arrêtées (fondateur)

| Décision | Choix retenu | Statut |
|---|---|---|
| Hébergement | **Garder Fly.io (back) + Vercel (front)** — pas de migration | Arrêté |
| Domaine définitif | **`coherence-metz.fr`** (extension `.fr`) | **Acquis** (OVH, 2026-06-09) |
| Environnement de test | **Staging dédié complet** (app Fly + base + analytics + sous-domaines séparés) | Arrêté |

**Pourquoi `coherence-metz.fr` et pas `coherence-immo.fr`** : un réseau immobilier
existant opère déjà sous la marque « Coherence Immobilier » sur `coherence-immo.com`
(+ « Agence Cohérence », « Maisons Cohérence » à Blois). Reprendre `coherence-immo`
créerait une **confusion de marque dans le même secteur** et un risque d'antériorité.
`coherence-metz` lève la collision **et** renforce l'ancrage local Metz/Moselle, qui
est le différenciateur du produit et le périmètre du forecast à 6-12 mois.

**Pourquoi garder Fly + Vercel** : le forecast (§5) établit que l'infra n'est pas une
contrainte (< ~6 €/mois même en scénario ambitieux). Le split actuel est gratuit, déjà
outillé en CI/CD, et adapté. Migrer maintenant serait prématuré. Les vrais risques
infra sont l'abus de `/analyze` (→ rate-limit, dette #2) et le cold-start (crédibilité),
pas l'hébergeur.

---

## 1. Pourquoi un env de test isolé, maintenant

La spec 9.10 instrumente le trafic pour produire un **funnel et un CAC chiffrés** sur
la prod (FORECAST §7). Si le trafic de test (founder, agents de l'atelier, itérations
de features) tombe dans la **même instance d'analytics et la même base** que la prod,
il **pollue les métriques d'adoption** — le seul KPI qui compte à 6-12 mois. Un
environnement de test séparé est donc la **condition d'intégrité du signal** que 9.10
doit collecter, pas un confort. Bénéfice secondaire : il protège la prod que l'on
promeut pendant le roll-out (démos partenaires/presse, cf. cold-start §5.4 du forecast).

---

## 2. Architecture cible (prod + staging)

| Couche | Prod | Staging | Coût marginal |
|---|---|---|---|
| Front (Vercel) | branche `main` → `coherence-metz.fr` (+ `www`) | branche `staging` → `staging.coherence-metz.fr` | 0 € (tier gratuit) |
| Back (Fly) | `backend-frosty-sound-441-docker` → `api.coherence-metz.fr` | **nouvelle app** `coherence-staging` → `api-staging.coherence-metz.fr` | ~0 € (auto-stop) |
| Base comparables | volume `comparables_data` (~17,7k lignes) | volume dédié, **amorcé d'un snapshot prod**, rafraîchi ponctuellement | ~0,15 €/mois (volume) |
| Analytics 9.10 | table `events` du SQLite prod | table `events` du **SQLite staging** (volume dédié) → **isolée par construction** | 0 € |
| Secrets | clés prod | `ADMIN_TOKEN` + clé OpenAI (idéalt avec usage-limit propre) **distincts** | 0 € |

> **Point critique — RÉSOLU par l'architecture choisie.** La 9.10 (mergée sur `main`)
> stocke les events dans une **table `events` du SQLite du backend** (`db/models.py`,
> endpoint `POST /events`), pas dans un outil analytics externe partagé. Comme le staging
> est un **backend Fly dédié avec son propre volume/SQLite**, ses events sont **physiquement
> isolés** de ceux de prod **sans aucune modification du schéma 9.10**. Seule précaution :
> le front staging **et les previews Vercel** doivent pointer vers le **backend staging**
> (`NEXT_PUBLIC_API_URL`), jamais vers le backend prod, sinon leur trafic de test
> écrirait dans la table `events` de prod. (Voir §8 : env var par environnement Vercel.)
>
> **Données staging** : sans comparables, le pilier prix renvoie « Indéterminé » et le
> test n'a aucune valeur. On amorce la base staging d'un **snapshot de la prod** (copie
> du volume ou export → `POST /admin/comparables` sur staging). Rafraîchissement
> ponctuel (manuel ou variante mensuelle de `collect.yml`). Les comparables ne sont pas
> des données sensibles → un snapshot est acceptable.

---

## 3. Flux de promotion (branches → environnements)

Adapté au mode solo + atelier d'agents, léger :

```
claude/<feature>   → PR (preview Vercel éphémère automatique)
       ↓ merge
staging            → déploie staging (front Vercel + back Fly coherence-staging)
       ↓ promotion quand vert
main               → déploie prod (front Vercel + back Fly prod) — l'existant
```

- Les **previews Vercel** par PR restent disponibles pour un check front rapide
  (déjà couvertes par la regex CORS `*.vercel.app`).
- `staging` est la branche d'**intégration validée** avant promotion vers `main`.
- `deploy-backend.yml` est étendu : un push sur `staging` touchant `backend/**`
  déploie l'app `coherence-staging` (en plus du comportement `main` → prod actuel).

---

## 4. Carte des URL définitives

| Usage | URL | Pointe vers |
|---|---|---|
| Front prod | `coherence-metz.fr` (+ `www`) | Vercel |
| API prod | `api.coherence-metz.fr` | Fly (app prod) |
| Front staging | `staging.coherence-metz.fr` | Vercel (branche `staging`) |
| API staging | `api-staging.coherence-metz.fr` | Fly (app `coherence-staging`) |
| Expéditeur email (plus tard, 9.2/9.6) | `coherence-metz.fr` + SPF/DKIM | Resend |

Pendant la transition, les anciennes URL `*.fly.dev` et `*.vercel.app` **continuent de
fonctionner** → bascule sans coupure.

---

## 5. Implémentation — qui fait quoi

### 5.1 Actions humaines (fondateur)
1. **Acheter `coherence-metz.fr`** (registrar : OVH, français/aligné local, ou autre ;
   ~10-15 €/an `[HYPOTHÈSE prix]`). Vérifier la disponibilité réelle à ce moment-là
   (non confirmable depuis l'environnement de dev : egress RDAP/AFNIC bloqué, HTTP 403).
2. Décider la **gestion DNS** : recommandation **Cloudflare** (gratuit, apex-flattening
   propre que Vercel/Fly apprécient), même si le domaine est acheté chez OVH.
3. Valider un **usage-limit OpenAI** distinct (ou clé distincte) pour staging, pour
   qu'un test ne consomme pas le quota prod (FORECAST §3.3 / §5.2).

### 5.2 In-repo — FAIT (branche `claude/focused-ramanujan-54ea89`)
1. **CORS** (chantier A) : domaines custom ajoutés à la liste par défaut dans
   `backend/app/main.py` (`coherence-metz.fr`, `www.`, `staging.`) + regex `*.vercel.app`
   conservée pour les previews. Effectif en prod au merge sur `main`. ⚠️ Sans ça le front
   prod sur le domaine custom aurait été bloqué par CORS.
2. **Config Fly staging** (chantier B) : `backend/fly.staging.toml` (app `coherence-staging`,
   volume dédié, mêmes healthcheck/auto-stop que la prod).
3. **CI/CD** (chantier B) : `deploy-backend.yml` étendu — push sur `staging` touchant
   `backend/**` → deploy `coherence-staging` (`--config fly.staging.toml`) ; push `main`
   → prod (inchangé) ; concurrency par environnement.

### 5.3 Actions externes — FAIT (2026-06-11, dashboards / CLI)
1. **Domaine** : `coherence-metz.fr` acheté chez OVH, DNS géré chez OVH.
2. **Vercel** : `coherence-metz.fr` + `www` (→ apex, redirect 308) en Production ;
   `staging.coherence-metz.fr` sur la branche `staging` (Preview).
3. **Env Vercel par environnement** : `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_SITE_URL`
   scindées **Production** (`api.` / apex) **et** **Preview** (`api-staging.` /
   `staging.`). Le redeploy `staging` a inliné les valeurs Preview → vérifié dans
   l'onglet Network (requête `/analyze` part bien vers `api-staging.coherence-metz.fr`).
4. **Fly staging** : `coherence-staging` créée + volume `comparables_data` + secrets
   `OPENAI_API_KEY`/`ADMIN_TOKEN` propres (staged au 1ᵉʳ deploy).
5. **DNS OVH** (Zone DNS) : apex `A 216.198.79.1` ; `www A 216.198.79.1` ;
   `api A 66.241.125.182` + `AAAA 2a09:8280:1::112:836d:0` ;
   `api-staging A 66.241.124.250` + `AAAA 2a09:8280:1::124:5032:0` ;
   `staging CNAME <cible-unique>.vercel-dns-017.com.`.
   *Piège rencontré* : un CNAME OVH refuse de cohabiter avec un autre champ — le TXT
   de parking « welcome » sur `www` bloquait ; contourné en mettant `www` en **A**
   (cohabite avec le TXT) plutôt qu'en CNAME.
6. **Certs Fly** : `api.` et `api-staging.coherence-metz.fr` émis (Let's Encrypt, actifs).
7. **`FLY_API_TOKEN`** remplacé par un **jeton org-scoped** (accès aux 2 apps).
8. **Seed staging** : secret repo `STAGING_ADMIN_TOKEN` créé ; workflow
   `.github/workflows/collect-staging.yml` lancé (success) → base staging peuplée.

> **Note données 9.10** : pendant la fenêtre où le front staging tapait encore l'API
> prod (avant le redeploy Preview), **quelques events de test ont été écrits dans la
> table `events` de prod**. Volume négligeable et antérieur au roll-out ; retenir le
> 2026-06-11 comme début de comptage propre si l'on veut des métriques pures.

### 5.4 Migration domaine sans coupure (ordre suivi)
1. Achat domaine + DNS chez le provider choisi.
2. Ajouter `coherence-metz.fr` + `www` au projet Vercel → poser les enregistrements DNS → Vercel émet le cert.
3. `fly certs add api.coherence-metz.fr` + enregistrements DNS → Fly émet le cert.
4. Mettre à jour `NEXT_PUBLIC_API_URL` (Vercel) et `CORS_ORIGINS` (Fly secrets/env).
5. Vérifier de bout en bout sur le domaine custom ; les anciennes URL restent valides en filet.
6. Répéter pour les sous-domaines `staging.` / `api-staging.`.

---

## 6. Séquencement vis-à-vis de la spec 9.10

- **9.10 mergée sur `main`.** Events stockés en table `events` du SQLite backend → la
  séparation d'env est **automatique** dès lors que staging est un backend dédié (§2).
  **Aucune retouche du schéma 9.10 nécessaire.**
- Ordre restant : (a) câbler le domaine prod (chantier A : Vercel + DNS OVH + `fly certs`
  + CORS déjà prêt) ; (b) stand-up staging (chantier B : créer l'app + volume + secrets,
  brancher `staging.`/`api-staging.`, seed). Le domaine débloque en plus l'email (9.2),
  l'auth/magic-link (9.6) et les canonicals SEO (9.5) — cf. FORECAST §6 et §10 item 7.

---

## 7. Points ouverts

- ~~Disponibilité réelle de `coherence-metz.fr`~~ → **acquis chez OVH** (2026-06-09).
  DNS géré chez OVH (bascule Cloudflare possible plus tard, optionnelle).
- ~~Séparation analytics staging/prod~~ → **résolue + vérifiée** (DB SQLite dédiée côté
  staging ; Preview Vercel pointe sur `api-staging.`, confirmé via l'onglet Network).
- Cadence de rafraîchissement des comparables staging (one-shot vs cron mensuel) `[HYPOTHÈSE — à fixer]`.
- Politique réseau de l'env staging : autoriser l'egress vers `api-adresse.data.gouv.fr`
  (géocodage couche C) et OpenAI, comme en prod (cf. `backend/CLAUDE.md` §11bis).
- **Débloqués par le domaine, à faire plus tard** : email/Resend + SPF/DKIM (9.2),
  canonicals SEO (9.5), auth magic-link (9.6).

---

## 8. État livré (2026-06-11)

| | Prod | Staging |
|---|---|---|
| Front (Vercel) | `coherence-metz.fr` (+ `www`→apex) | `staging.coherence-metz.fr` (branche `staging`) |
| API (Fly) | `api.coherence-metz.fr` → `backend-frosty-sound-441-docker` | `api-staging.coherence-metz.fr` → `coherence-staging` |
| Base / events 9.10 | SQLite prod | SQLite staging — **isolé** (vérifié) |
| Deploy | merge `main` → `deploy-backend.yml` (prod) | push/run `staging` → `deploy-backend.yml` (staging) |
| Seed comparables | `collect.yml` (hebdo) | `collect-staging.yml` (manuel) |

TLS Let's Encrypt actif sur les 4 hôtes. Anciennes URL `*.fly.dev` / `*.vercel.app`
conservées en filet. Flux de travail : `claude/* → PR → staging` (test sur
`staging.coherence-metz.fr`) `→ main` (prod).
