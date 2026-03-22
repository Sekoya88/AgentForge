# AgentForge — Que tester sur le front (pour de vrai)

Ce document décrit des **parcours manuels** qui valident des **chaînes complètes** (API + DB + orchestration), pas seulement “la page s’affiche”. Adapte les URLs si ton front n’est pas sur `http://localhost:3000`.

## Avant de commencer

1. **Infra** : Postgres à jour (`alembic upgrade head`), **Redis** si tu veux async + SSE fiables.
2. **`.env` racine** : `JWT_SECRET_KEY` ; pour les scénarios LLM / RAG / génération : `OPENAI_API_KEY` (et éventuellement `GOOGLE_API_KEY` pour Gemini sur les nœuds LLM).
3. **CORS** : `CORS_ORIGINS` doit inclure l’origine exacte du navigateur (`http://localhost:3000` *et* `http://127.0.0.1:3000` si tu changes).

---

## 1) Auth et session UI (régression réelle)

**But :** vérifier que le client et l’UI partagent le même état de session.

1. **Register** puis **Login**.
2. Navigue vers **Agents** : la liste charge sans 401.
3. Vérifie le header : tu dois voir **Sign out** (pas “Login” fantôme).
4. **Sign out** puis recharge : les routes protégées renvoient vers login.

*Si ça casse, le bug est souvent `localStorage` / header — pas “juste” un style.*

---

## 2) Golden path RAG (Knowledge → graphe → exécution)

**But :** prouver que **tes données** passent par **embeddings → Postgres → tool `retrieve` → réponse agent**.

1. Va sur **Knowledge** : colle un texte **factuel** que seul ce corpus contient (ex. un paragraphe avec un code interne fictif `AF-TEST-7741`).
2. **Index** avec un titre clair ; vérifie qu’une source apparaît avec un nombre de chunks > 0.
3. **Agents → New agent** :
   - Provider **mock** pour l’instant (on teste surtout le tool ; pour une réponse “intelligente” sur le contenu récupéré, passe en **OpenAI** sur le nœud LLM).
   - Dans `graph_definition`, graphe minimal du type :
     - nœud **tool** avec `"tool_name": "retrieve"` (optionnel : `"top_k": 3` dans `config`),
     - en **entry_point** sur ce nœud, ou enchaînement LLM → tool selon ton besoin.
   - **Execute** avec la case **Stream logs** **désactivée** (exécution sync, moins dépendante de Redis).
4. Message utilisateur : une question qui **cite** ou **requiert** l’info `AF-TEST-7741`.

**Succès :** la sortie contient un extrait cohérent avec ton texte indexé (via le résultat du tool `retrieve`).
**Échec typique :** clé OpenAI absente (embeddings), aucun chunk indexé, ou `tool_name` ≠ `retrieve`.

---

## 3) Skill métier + attachement (registry + subprocess)

**But :** valider **validation statique**, **stockage**, **liaison agent**, **exécution** d’un outil utilisateur.

1. **Skills → New** : code Python avec `def run(x: str) -> str:` qui transforme l’entrée (ex. majuscules).
2. Crée l’agent ; coche la skill ; dans le JSON, nœud **tool** avec `"tool_name": égal au name exact du skill**.
3. **Execute** (sync de préférence) avec un message court.

**Succès :** message assistant contenant le résultat attendu de `run()`.
**Échec typique :** nom du tool ≠ `name` du skill, skill non cochée, erreur de validation (`validate` sur la skill si tu veux isoler).

---

## 4) Red-team : comprendre ce que tu mesures

**But :** ne **pas** confondre **démo** et **sécurité réelle**.

1. Sur la fiche agent, **Run red-team** (ou flow campagnes).
2. Avec **`REDTEAM_MODE=mock`** (défaut) : tu obtiens un **score et un rapport structurés**, mais les “tests” sont **synthétiques** — utile pour **CI / régression UI / pipeline**, pas pour prouver la résistance réelle du prompt.
3. Pour une valeur sécu : backend avec **Node + `npx`**, `REDTEAM_MODE=promptfoo`, et interpréter les rapports en connaissance de cause.

**Succès pertinent ici :** campagne **completed**, score écrit sur l’agent, historique visible ; tu sais expliquer **mock vs promptfoo** à quelqu’un d’autre.

---

## 5) Streaming (optionnel mais non trivial)

**But :** Redis + SSE + persistance d’exécution.

1. Redis up, **Stream logs** coché, **Execute**.
2. Vérifie les événements dans l’UI ; en cas d’échec, le symptôme est souvent 503 / pas d’events — **pas** un simple bug CSS.

---

## 6) Builder (régression graphe)

**But :** le graphe édité **sauvegarde** et **ré-exécute** comme attendu.

1. Ouvre **Open builder** depuis un agent, déplace un nœud ou change une condition d’edge, **sauvegarde**.
2. Recharge la page agent : définition toujours alignée ; **Execute** un scénario minimal.

---

## Ce qui ne “prouve” pas grand-chose seul

- Ouvrir **Finetune** et voir un job **pending** : normal — **l’entraînement GPU n’est pas branché** (Labs).
- Lancer uniquement **Sandbox** sans enchaîner avec un agent : utile pour du code ad hoc, pas pour la valeur produit “agent + politique + skills”.
- **Mock** red-team : utile pour **pipeline**, pas pour une audit sécu.

---

## Résumé

| Parcours | Ce que ça valide |
|----------|------------------|
| Auth + header | JWT, CORS, UX session |
| Knowledge + `retrieve` | pgvector, embeddings, tool, exécution |
| Skill attachée | Registry, graphe, subprocess skill |
| Campagnes | Jobs red-team, scores, **interprétation** mock vs réel |
| SSE | Redis, async execute |
| Builder | Persistance `graph_definition` |

Pour automatiser une partie de ça en CI, voir `frontend/e2e/golden-path.spec.ts` et `CONTRIBUTING.md`.
