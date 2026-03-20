# AgentForge — inventaire écrans pour Stitch (Material / Google Design)

Document de référence pour produire des maquettes **cohérentes** dans **Stitch**, alignées sur l’app Next.js actuelle (`frontend/src/app`) et la roadmap (`.planning/STATE.md`, `README.md`).

---

## 1. Fondations design (à faire en premier)

| ID | Livrable Stitch | Objectif |
|----|-----------------|----------|
| **DS-01** | **Tokens & typographie** | Couleurs (accent + surfaces + états), text styles (display / title / body / label / code), rayons, élévation. |
| **DS-02** | **Composants de base** | Boutons (filled / outlined / text), champs texte, textarea, select, checkbox/switch, badges (statut agent / exécution), cartes list item. |
| **DS-03** | **Feedback** | Bannières d’erreur / warning / info, états vide (illustration + CTA), skeletons list / détail. |
| **DS-04** | **Navigation** | Header app (logo, liens, zone user), option sidebar future (voir §8). |

**Cohérence** : même header, même largeur de contenu (`max-w` équivalent), même accent sur les CTA primaires (aujourd’hui cyan dans le code — à trancher avec la palette Material/Stitch).

---

## 2. Shell applicatif (toutes les pages “connectées”)

| Page Stitch | Route cible | Contenu à maquetter |
|-------------|-------------|---------------------|
| **APP-SHELL** | `layout` global | Header : **AgentForge** → `/`, nav **Agents · Sandbox · Campaigns · Skills · Finetune**, **Login · Register** (ou avatar + menu quand session). Zone `<main>` avec padding. |
| **APP-SHELL-AUTH** | (comportement) | Variante header : lien **Logout**, pas de double Login/Register ; option menu utilisateur (email, settings). *À designer même si pas encore implémenté en code.* |

---

## 3. Marketing & onboarding

| ID | Route | Priorité | Contenu / états |
|----|-------|----------|-----------------|
| **P01** | `/` | Haute | Hero : titre, pitch court, CTA **Open agents**, **Create account**. Fond sombre cohérent avec le reste. |
| **P02** | `/login` | Haute | Formulaire email + mot de passe, lien vers register, message d’erreur auth. |
| **P03** | `/register` | Haute | Formulaire inscription (email, password, display name si présent en API), lien vers login, erreurs validation. |

---

## 4. Agents (cœur produit)

| ID | Route | Priorité | Contenu / états |
|----|-------|----------|-----------------|
| **A01** | `/agents` | Haute | Liste agents : titre, **New agent**, liste (nom, statut), **empty state** (“No agents yet”), état **non authentifié** (message + CTA login). |
| **A02** | `/agents/new` | Haute | Création : nom, **graph_definition** (JSON textarea large), aide inline / lien doc ; bouton Create ; erreur JSON invalide. |
| **A03** | `/agents/[id]` | Haute | **Fiche agent** : nom, infos, **model_config** (lecture ou résumé), champ message utilisateur, toggle sync/async + stream, bouton Run, **log d’exécution** / SSE (zone scroll), dernier statut (running / completed / paused), actions **export** / lien **builder** / lancement campagne si présent. |
| **A04** | `/agents/[id]/builder` | Très haute | **Canvas graphe** (style React Flow) : palette nœuds (llm, tool, subagent, conditional, interrupt), mini-map, contrôles zoom, **entry point**, édition **condition** sur edges, barre **Save** + message succès/erreur. *Frame desktop large recommandée.* |

**États transverses agents** : chargement (skeleton), 404 agent, erreur API.

---

## 5. Sandbox

| ID | Route | Priorité | Contenu / états |
|----|-------|----------|-----------------|
| **S01** | `/sandbox` | Moyenne | Zone code Python, timeout, mode sync/async, résultat stdout/stderr / stream, avertissement **non sécurisé pour prod** (disclaimer visible). |

---

## 6. Campagnes (red-team)

| ID | Route | Priorité | Contenu / états |
|----|-------|----------|-----------------|
| **C01** | `/campaigns` | Moyenne | Liste campagnes, création (formulaire selon champs API), empty state. |
| **C02** | `/campaigns/[id]` | Moyenne | Détail campagne, **rapport** (mock ou réel), statut, lien vers agent cible. |

---

## 7. Skills

| ID | Route | Priorité | Contenu / états |
|----|-------|----------|-----------------|
| **K01** | `/skills` | Moyenne | Liste skills, CTA **New skill**, empty state. |
| **K02** | `/skills/new` | Moyenne | Formulaire création + action validate (stub) + retours succès/erreur. |

---

## 8. Fine-tuning

| ID | Route | Priorité | Contenu / états |
|----|-------|----------|-----------------|
| **F01** | `/finetune` | Moyenne | Liste jobs, états (queued / running / done), empty state. |
| **F02** | `/finetune/new` | Moyenne | Formulaire nouveau job (dataset, hyperparams selon API), CTA submit. |

---

## 9. Écrans transverses (à prévoir en Stitch)

| ID | Description | Usage |
|----|-------------|--------|
| **X01** | **HITL / interrupt** — modal ou panneau : décisions autorisées (approve / reject …), bouton confirmer, état “paused” sur fiche exécution. | Aligné nœud `interrupt` + `POST .../interrupt`. |
| **X02** | **Import agent** — upload ou collage JSON + preview + conflit de nom. | `POST /api/v1/agents/import`. |
| **X03** | **Settings compte** (optionnel code) | Email, changement mot de passe, clés API *côté serveur uniquement* (ne jamais exposer les secrets en UI). |
| **X04** | **404 / erreur globale** | Page simple cohérente avec le shell. |

---

## 10. Phase 2 design (roadmap — pas encore toutes en UI)

À planifier dans Stitch quand le produit avance (cf. `.planning/ROADMAP.md`, `STATE.md`) :

| ID | Écran | Notes |
|----|-------|--------|
| **R01** | Dashboard observabilité (traces, coûts tokens) | Langfuse / Sentry. |
| **R02** | Comparaison scores red-team / régressions | CI red-team. |
| **R03** | Détail job Modal fine-tune | métriques, logs GPU. |
| **R04** | **Navigation dense** : sidebar + breadcrumbs | Si le nombre d’écrans augmente. |

---

## 11. Ordre de production recommandé (Stitch)

1. **DS-01 → DS-04** (tokens + composants + nav).
2. **P01 → P02 → P03** (entrée produit).
3. **APP-SHELL** + **A01 → A02 → A03 → A04** (boucle valeur principale).
4. **S01**, **C01–C02**, **K01–K02**, **F01–F02**.
5. **X01–X04** (polish flux critiques).
6. **R01–R04** quand la roadmap le demande.

---

## 12. Checklist cohérence Stitch

- [ ] Même grille et marges sur toutes les pages “app”.
- [ ] CTA primaire unique par écran (sauf builder).
- [ ] États **empty / loading / error** explicites sur chaque liste.
- [ ] Terminologie stable : *Agent*, *Execution*, *Campaign*, *Skill*, *Finetune job*, *Sandbox*.
- [ ] Accessibilité : contrastes, focus visible, labels de formulaires.
- [ ] Mobile : au minimum **login / liste agents / détail agent** en vue étroite ; **builder** peut rester **desktop-first**.

---

## Référence code

| Zone | Chemin |
|------|--------|
| Routes | `frontend/src/app/**/page.tsx` |
| Layout & nav | `frontend/src/app/layout.tsx` |
| Composants exécution | `frontend/src/components/execution/` |

*Document généré pour alignement design AgentForge ↔ Stitch ; à faire évoluer quand de nouvelles routes sont ajoutées.*
