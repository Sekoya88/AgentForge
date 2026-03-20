# AgentForge — inventaire écrans Stitch (DNA landing)

Document pour produire des maquettes **Stitch** alignées sur les routes Next.js (`frontend/src/app`) **et** sur le **même langage visuel** que la landing AgentForge (référence HTML/Tailwind : fond `#06060E`, JetBrains Mono, accents lavender / teal, aurora, header glass). **Chaque frame Stitch doit appliquer ce DNA** — pas seulement la home.

---

## 1. DNA visuel — à réutiliser sur *toutes* les pages

Copier ces règles dans le prompt Stitch ou en note de fichier projet.

### 1.1 Couleurs (tokens)

| Rôle | Valeur / token | Usage |
|------|----------------|--------|
| **Background app** | `#06060E` | Fond page global. |
| **Texte principal** | `#e4e1ee` (`on-surface`) | Titres corps, labels importants. |
| **Texte secondaire** | `#8888AA` | Nav inactive, descriptions, meta. |
| **Texte tertiaire** | `#555566` | Placeholders, hints, kicker sections. |
| **Bordures** | `#1E1E30`, `border-white/10` | Cartes, séparateurs, header. |
| **Surface / panneaux** | `#12121E`, `#1b1b24`, `#1f1f28` | Inputs, pills, tags, zones de contenu. |
| **Primary (lavender)** | `#c3c0ff` | CTA secondaires texte, liens « Get started », mots en serif dans titres, barres de benchmark « meilleur ». |
| **Tertiary (teal)** | `#3cddc7` | Accent alternatif (titres serif, hovers footer type teal-400). |
| **Secondary (mauve)** | `#d2bbff` | Accent serif secondaire (ex. section *innovator*). |
| **CTA primaire fort** | Fond `#e4e1ee` (inverse-surface), texte `#13121c` (surface-dim) | Bouton type « Open agents » / « Get Started » header. |
| **CTA hero final** | Fond blanc, texte `#06060E` | Grand CTA type « START NOW » si besoin. |
| **Erreur** | `#ffb4ab` / conteneur erreur sombre | Messages formulaire, bannières. |

*(Tu peux mapper les noms sémantiques du HTML Tailwind : `primary`, `tertiary`, `surface`, `on-surface`, etc.)*

### 1.2 Typographie

| Usage | Police | Détail |
|-------|--------|--------|
| **UI, body, nav, boutons** | **JetBrains Mono** | 11–16px selon hiérarchie ; tracking serré sur titres. |
| **Accent éditorial dans H1/H2** | **Georgia** (serif) *italic* | 1 mot clé par gros titre (ex. *secure*, *unstoppable*, *performance*) en `primary` ou `tertiary`. |
| **Option display** | Space Grotesk | Réservé si besoin d’un second niveau ; sinon rester mono pour cohérence « dev tool ». |

### 1.3 Atmosphère & layout

- **Aurora** : 2–3 blobs flous (`blur` fort), indigo `#4F46E5`, violet `#7C3AED`, teal `#2DD4BF`, opacité faible, en `absolute` derrière le contenu (`z-0`), **sur les pages app aussi** (intensité réduite si besoin pour lisibilité).
- **Contenu** : `relative z-10` ; largeur max type **`max-w-7xl`** pour sections riches, **`max-w-5xl`** pour formulaires / listes denses (aligné app actuelle).
- **Section kickers** : libellés type `[ CORE FEATURES ]` — uppercase, **11px**, `#555566`, `tracking-[0.2em]`, **bold**, au-dessus des H2.
- **H2** : ~30px bold blanc + **un mot serif italic** coloré (`primary` / `tertiary` / `secondary`).

### 1.4 Composants récurrents

| Pattern | Spec Stitch |
|---------|-------------|
| **Header** | Fixe, hauteur ~64px, `bg-[#06060E]/60`, `backdrop-blur-xl`, `border-b border-white/10`, ombre légère. Logo **AgentForge** mono bold blanc. Nav : lien actif blanc semibold, autres `#8888AA` → hover blanc. Droite : **Login** texte + **Get Started** (inverse surface / fond clair sur texte sombre). |
| **Champ type command palette** | Pill `rounded-full`, fond `#12121E`, bordure `#1E1E30`, icône Material **search**, chips optionnels. |
| **Bouton primaire (app)** | Même logique que hero : fond clair `on-surface`, texte `surface-dim`, `rounded-xl`, hover glow indigo léger. |
| **Bouton secondaire** | `border border-[#2A2A3A]`, texte blanc, `rounded-xl`, hover `bg-white/5`. |
| **Cartes liste** | Bordure `#1E1E30`, fond discret ou transparent ; hover léger ; texte mono. |
| **Tags / badges** | Petit pill `bg-[#1E1E30] text-[#8888AA] text-[10px]` (statuts agent, catégories). |
| **Accordéon** | Bordures horizontales `#1E1E30`, titre blanc, replié `white/60` + icône `add` / ouvert `remove` (Material Symbols). |
| **Barres de métrique** | Barre active `bg-primary`, autres `bg-[#1E1E30]`, `h-2 rounded-full` — réutilisable pour scores, latence, coûts dans **C02**, **A03**. |
| **Cartes produit (4-col)** | Bandeau haut dégradé indigo → violet → teal, `rounded-xl`, tag + titre + desc `#8888AA` + lien `text-primary` « Get started > ». Adapter en **cartes feature** sur pages internes. |
| **Footer** (marketing / option app) | `border-t border-[#1E1E30]`, colonnes mono, liens `#555566` hover teal. |

### 1.5 Icônes

- **Material Symbols Outlined** (Google Fonts) — cohérent avec l’écosystème Material / Stitch.

### 1.6 Mode

- **Dark only** (`class="dark"` équivalent) — pas de thème clair dans ce contrat.

---

## 2. Fondations Stitch (premiers livrables)

| ID | Livrable | Contenu |
|----|----------|---------|
| **DS-01** | **Tokens Stitch** | Importer §1.1–1.2 comme variables couleur + styles de texte. |
| **DS-02** | **Composants** | Header DNA, boutons §1.4, input/textarea (bordure `#1E1E30`, fond `#12121E`), select, checkbox, badge tag, carte liste, modal (fond panneau + blur léger). |
| **DS-03** | **Feedback** | Bannière erreur, empty state (kicker + H2 + serif + CTA), skeletons lignes mono. |
| **DS-04** | **Page blanche app** | Shell : header + `main` avec aurora atténuée + `max-w-5xl` / `7xl`. |

**Règle** : abandonner l’ancien accent cyan isolé du code legacy ; **tout nouveau design suit §1**.

---

## 3. Shell applicatif

| Page Stitch | Route | DNA à appliquer |
|-------------|-------|-----------------|
| **APP-SHELL** | Layout global | Header **identique §1.4** ; nav **Agents · Sandbox · Campaigns · Skills · Finetune** ; **Login** + **Get Started** (→ register). `main` avec padding horizontal généreux, aurora discret. |
| **APP-SHELL-AUTH** | Session active | Même header ; remplacer Login/Get Started par **avatar ou email** + menu (**Logout**, option **Settings**). Lien actif de section en blanc. |

---

## 4. Marketing & onboarding

| ID | Route | Contenu + DNA |
|----|-------|----------------|
| **P01** | `/` | **Référence complète** : hero (pill recherche optionnelle), H1 avec serif *secure*, sous-titre `#8888AA` mono, double CTA §1.4, scroll hint, sections **Advantages** (split + accordéon), **Core features** (grid 4 col + kicker), **Benchmarks** (barres), **Products** (cartes dégradé), **CTA final** blanc, **footer** §1.4. |
| **P02** | `/login` | Fond `#06060E` + aurora. Kicker `[ SIGN IN ]`. H2 avec un mot *italic* serif `primary`. Carte formulaire `glass-panel` ou bordure `#1E1E30`, champs mono, CTA primaire §1.4, lien register en `text-primary`. Erreur couleur error token. |
| **P03** | `/register` | Même schéma que P02 ; kicker `[ CREATE ACCOUNT ]` ; champs + validation. |

---

## 5. Agents

| ID | Route | Contenu + DNA |
|----|-------|----------------|
| **A01** | `/agents` | Kicker `[ AGENTS ]`. H2 « Your *fleet* » (serif sur *fleet* ou équivalent). Bouton **New agent** = CTA primaire clair. Liste : lignes type bordure `#1E1E30` ; empty state avec serif au choix + CTA. Non auth : message `#8888AA` + bouton Get Started. |
| **A02** | `/agents/new` | Kicker `[ NEW AGENT ]`. Titre + textarea JSON large (fond `#12121E`, font mono). Aide inline `#555566`. Primary submit. Erreur JSON bannière. |
| **A03** | `/agents/[id]` | Kicker `[ AGENT ]` + nom. Panneaux `border-[#1E1E30]` pour model_config, input user (style pill ou champ §1.4), toggles stream/async. Zone log : fond `surface-container`, texte mono petit, scroll. Barres ou badges pour statut (running / paused / completed) couleur primary/tertiary. Boutons secondaires outline. |
| **A04** | `/agents/[id]/builder` | **Desktop-first**, `max-w` full ou très large. Toolbar glass en haut (Save = CTA primaire). Canvas sombre `#0d0d16` ou `surface-dim` ; nœuds bordure `#1E1E30`, accent teal sur sélection ; palette latérale type cartes compactes. Mini-map discrète. |

**États** : skeleton lignes ; 404 avec H2 + serif + lien retour ; erreur API bannière.

---

## 6. Sandbox

| ID | Route | Contenu + DNA |
|----|-------|----------------|
| **S01** | `/sandbox` | Kicker `[ SANDBOX ]`. Éditeur code (monospace, fond sombre). Disclaimer **visible** : bordure `error` ou fond `error-container` très sombre, texte clair. CTA run = primaire. Zone résultat mono `#8888AA`. |

---

## 7. Campagnes

| ID | Route | Contenu + DNA |
|----|-------|----------------|
| **C01** | `/campaigns` | Kicker `[ CAMPAIGNS ]`. Liste cartes ou table stylée §1.4 ; empty state DNA. |
| **C02** | `/campaigns/[id]` | Rapport : réutiliser **barres horizontales** type benchmark pour scores si pertinent ; titres avec serif optionnel ; meta `#8888AA`. |

---

## 8. Skills

| ID | Route | Contenu + DNA |
|----|-------|----------------|
| **K01** | `/skills` | Kicker `[ SKILLS ]`. Liste + CTA New skill primaire ; empty DNA. |
| **K02** | `/skills/new` | Formulaire dans carte bordée ; validate = secondaire ou primaire selon hiérarchie. |

---

## 9. Fine-tuning

| ID | Route | Contenu + DNA |
|----|-------|----------------|
| **F01** | `/finetune` | Kicker `[ FINE-TUNE ]`. Liste jobs + badges statut (`#1E1E30` tags). |
| **F02** | `/finetune/new` | Formulaire long ; sections séparées par `border-[#1E1E30]` comme accordéon visuel (sans forcément être interactif). |

---

## 10. Écrans transverses

| ID | Description | DNA |
|----|-------------|-----|
| **X01** | Modal / drawer HITL (approve / reject) | Fond panneau `#1f1f28` ou glass, bordure `#1E1E30`, boutons primaire / outline. |
| **X02** | Import agent JSON | Zone drop ou textarea monospaced ; preview dans carte secondaire. |
| **X03** | Settings compte | Même pattern que login ; pas d’affichage de secrets. |
| **X04** | 404 | Minimal : H1 + serif + lien `text-primary` accueil. |

---

## 11. Phase 2 (roadmap)

| ID | Écran | DNA |
|----|-------|-----|
| **R01** | Observabilité | Grids + barres métriques §1.4 ; kickers sections. |
| **R02** | Comparaison red-team | Tableaux sombres, barres primary vs `#1E1E30`. |
| **R03** | Job Modal / GPU | Logs en mono, cartes métriques. |
| **R04** | Sidebar dense | Même couleurs ; items nav `8888AA` / actif blanc. |

---

## 12. Ordre de production Stitch

1. **DS-01 → DS-04** (tokens + composants du §1).
2. **P01** (landing complète = référence pixel).
3. **APP-SHELL** + **P02–P03**.
4. **A01 → A04**.
5. **S01**, **C01–C02**, **K01–K02**, **F01–F02**.
6. **X01–X04**, puis **R01–R04**.

---

## 13. Checklist qualité (chaque export Stitch)

- [ ] Fond `#06060E` + au moins **aurora léger** sur pages app.
- [ ] **JetBrains Mono** dominant + **1 serif italic** sur H1/H2 principaux.
- [ ] Header **glass** + bordure `white/10` comme landing.
- [ ] Kickers `[ SECTION ]` sur les pages outil (pas obligatoire sur modales).
- [ ] CTA primaire = **clair sur foncé** (équivalent Open agents / Get Started).
- [ ] Bordures `#1E1E30` sur cartes / split.
- [ ] **Material Symbols** pour + / − / search / chevron.
- [ ] États empty / error / loading visibles.
- [ ] Mobile : login, listes, détail agent ; builder desktop-first.

---

## 14. Références

| Type | Emplacement |
|------|-------------|
| Routes implémentées | `frontend/src/app/**/page.tsx` |
| Layout actuel (à faire converger vers DNA) | `frontend/src/app/layout.tsx` |
| Landing HTML / Tailwind (source DNA) | Fourni par l’équipe / export Stitch — **ne pas diverger** des §1.x |

*Document vivant : toute nouvelle route = nouvelle ligne avec colonne « Contenu + DNA ».*
