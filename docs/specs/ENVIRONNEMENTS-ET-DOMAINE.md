# Environnements (test/prod) & domaine définitif — plan de déploiement

> **Nature de ce document.** Plan d'infra que tu possèdes et édites, lié au roll-out
> de Cohérence (cf. `docs/strategy/FORECAST.md` §7 et la spec 9.10 « monitoring du
> trafic / events » en cours d'écriture). Il fixe deux décisions structurantes :
> (1) un **environnement de test isolé de la prod**, (2) le **domaine définitif** et
> l'hébergement. Les valeurs non sourcées sont marquées `[HYPOTHÈSE]`.
>
> **Dernière mise à jour** : 2026-06-09.

---

## 0. Décisions arrêtées (fondateur)

| Décision | Choix retenu | Statut |
|---|---|---|
| Hébergement | **Garder Fly.io (back) + Vercel (front)** — pas de migration | Arrêté |
| Domaine définitif | **`coherence-metz.fr`** (extension `.fr`) | Arrêté — dispo à confirmer au registrar |
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
| Analytics 9.10 | bucket/instance prod | **bucket séparé** OU flag `env=staging` exclu des agrégats | dépend de l'outil 9.10 |
| Secrets | clés prod | `ADMIN_TOKEN`, clé OpenAI (idéalt avec usage-limit propre), token analytics **distincts** | 0 € |

> **Point critique** : la séparation **analytics** est non-négociable — c'est la raison
> d'être de l'env. Le choix d'outil 9.10 (table SQLite `events` maison vs Plausible/Umami,
> cf. FORECAST §7.1) doit prévoir dès le départ une **dimension `env`** ou deux buckets.
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

### 5.2 Ce que je peux préparer/implémenter
1. **App Fly staging** : `fly.staging.toml` (app `coherence-staging`, volume dédié,
   mêmes healthcheck/auto-stop), provisioning du volume, secrets staging.
2. **CI/CD** : étendre `deploy-backend.yml` (trigger `staging` → `coherence-staging`),
   configurer la branche de production Vercel = `main` + alias stable pour `staging`.
3. **CORS** : ajouter les domaines custom à `CORS_ORIGINS` côté Fly. ⚠️ **Sans ça, le
   front prod sur `coherence-metz.fr` est bloqué par CORS** — la config actuelle ne
   couvre que `localhost` + regex `*.vercel.app` (`backend/app/main.py:37-44`). À ajouter :
   `https://coherence-metz.fr`, `https://www.coherence-metz.fr`,
   `https://staging.coherence-metz.fr`.
4. **Env front** : `NEXT_PUBLIC_API_URL` → `https://api.coherence-metz.fr` (prod) et
   `https://api-staging.coherence-metz.fr` (staging) ; `NEXT_PUBLIC_SITE_URL` →
   `https://coherence-metz.fr` (prérequis des canonicals/sitemap SEO 9.5, FORECAST §6).
5. **Seed données staging** : script de snapshot prod → staging.
6. **Certs** : procédure `fly certs add api.coherence-metz.fr` (+ staging) une fois le
   DNS en place ; Vercel gère son cert automatiquement à l'ajout du domaine.

### 5.3 Migration domaine sans coupure (ordre)
1. Achat domaine + DNS chez le provider choisi.
2. Ajouter `coherence-metz.fr` + `www` au projet Vercel → poser les enregistrements DNS → Vercel émet le cert.
3. `fly certs add api.coherence-metz.fr` + enregistrements DNS → Fly émet le cert.
4. Mettre à jour `NEXT_PUBLIC_API_URL` (Vercel) et `CORS_ORIGINS` (Fly secrets/env).
5. Vérifier de bout en bout sur le domaine custom ; les anciennes URL restent valides en filet.
6. Répéter pour les sous-domaines `staging.` / `api-staging.`.

---

## 6. Séquencement vis-à-vis de la spec 9.10

- La **dimension `env`** (ou double bucket) doit être **dans la spec 9.10 dès l'écriture**
  — c'est le prérequis qui rend l'env de test utile sans repasse.
- Ordre conseillé : (a) 9.10 conçue avec la séparation d'env ; (b) stand-up staging
  (Fly app + DNS + CORS + seed) ; (c) bascule domaine prod. Le domaine débloque en plus
  l'email (9.2), l'auth/magic-link (9.6) et les canonicals SEO (9.5) — cf. FORECAST §6 et §10 item 7.

---

## 7. Points ouverts

- Disponibilité réelle de `coherence-metz.fr` (à confirmer au registrar).
- Choix d'outil analytics 9.10 (impacte la mécanique exacte de séparation d'env) — tranché dans la spec 9.10.
- Cadence de rafraîchissement des comparables staging (one-shot vs cron mensuel) `[HYPOTHÈSE — à fixer]`.
- Politique réseau de l'env staging : autoriser l'egress vers `api-adresse.data.gouv.fr`
  (géocodage couche C) et OpenAI, comme en prod (cf. `backend/CLAUDE.md` §11bis).
