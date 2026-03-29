# 🚀 Guide Complet d'Exploitation : AgentForge (A à Z)

Bienvenue dans le guide ultime de **AgentForge**. Ce document t'explique en détail l'architecture, comment lancer le projet entier avec une seule commande, l'utilité de chaque composant (comme Redis), comment tester le front, le back, et surtout comment utiliser les SDKs que nous avons créés dans d'autres dossiers et projets !

---

## 🏗️ 1. Architecture du Projet et Composants

AgentForge est un écosystème modulaire composé des éléments suivants :

1. **Backend (FastAPI)** : Le cœur du système. Il orchestre les agents, sauvegarde les versions (snapshots) en base de données, gère l'exécution des graphes, le streaming SSE (Server-Sent Events) et la boucle MLOps (Data Flywheel).
2. **Frontend (Next.js 15)** : L'interface utilisateur. Elle permet de visualiser et d'interagir avec les agents, de suivre les exécutions et potentiellement (à l'avenir) d'éditer le graphe visuellement via `reactflow`.
3. **Database (PostgreSQL + pgvector)** : Stocke les agents, les versions, les exécutions, le feedback utilisateur et les `finetune_examples`. Tourne sur le port `5433` de ton hôte.
4. **Redis** : Base de données en mémoire ultra-rapide. Il a deux rôles cruciaux dans AgentForge :
   - **Pub/Sub pour le Streaming SSE** : Quand un agent s'exécute, chaque étape du graphe est publiée dans Redis. Le backend lit ces événements et les streame en direct au front.
   - **File d'attente (Background Tasks)** : Utilisé pour gérer les tâches lourdes asynchrones, comme le polling de statut des jobs de fine-tuning chez Modal.
5. **SDKs (Python et TypeScript/JS)** : Les "clients" qui permettent aux développeurs de définir et déployer leurs agents programmatiquement *depuis leur propre code*.

### 🔍 Comment visualiser et comprendre Redis ?
Redis tourne via Docker sur le port `6380` (pour éviter les conflits avec un Redis local existant sur `6379`).
- **À quoi ça sert concrètement ?** Si deux utilisateurs discutent avec le même agent, Redis permet de router les messages de streaming uniquement vers la bonne connexion HTTP sans saturer le backend FastAPI.
- **Comment le visualiser ?**
  1. *Via le CLI Docker* : Tu peux taper dans ton terminal `docker exec -it <nom_du_container_redis> redis-cli`. Ensuite tape `MONITOR` pour voir toutes les commandes passer en temps réel (notamment les `PUBLISH` lors de l'exécution d'un agent).
  2. *Via une UI graphique (Recommandé)* : Télécharge et installe **[RedisInsight](https://redis.com/redis-enterprise/redis-insight/)**. Connecte-toi à `localhost` sur le port `6380`. Tu pourras explorer les clés en cache et les streams !

---

## 🚀 2. Lancement Rapide (Quick-Start)

J'ai ajouté une commande magique au `Makefile` pour tout lancer (Docker, Backend, Frontend) en une seule fois et en parallèle :

```bash
make quick-start
```

**Ce que fait cette commande :**
1. Elle lance Postgres et Redis via `docker compose` en arrière-plan.
2. Elle attend que Postgres soit prêt à accepter des connexions.
3. Elle joue les migrations de base de données (Alembic) si nécessaire.
4. Elle lance le **Backend FastAPI** (`http://localhost:8000`) via `uvicorn` et le **Frontend Next.js** (`http://localhost:3000`) dans ton terminal grâce à `npx concurrently`.

*Note : Pour arrêter tout ça, fais simplement `Ctrl+C`. Si tu veux couper les conteneurs en fond : `docker compose down`.*

---

## 💻 3. Comment utiliser les SDKs dans *d'autres dossiers et projets* ?

C'est là tout l'intérêt de construire des SDKs ! Tu peux tout à fait les importer dans des projets qui ne se trouvent **pas** dans le répertoire racine d'AgentForge.

### 🐍 Pour le SDK Python (`/sdk`)
Si tu as un projet Python ailleurs sur ton Mac (ex: `~/MesProjets/MonSuperAgent`) :
1. Va dans ton projet : `cd ~/MesProjets/MonSuperAgent`
2. Installe le SDK AgentForge localement en "mode éditable" :
   ```bash
   pip install -e /Users/nicolas/Documents/workspace/AgentForge/sdk
   ```
3. Tu peux maintenant utiliser `import agentforge` dans ton code !
4. N'oublie pas de définir ton token : `export AGENTFORGE_API_KEY="ton_token_genere_sur_le_swagger"`

### 🟦 Pour le SDK TypeScript/JS (`/sdk-js`)
Si tu as un projet Node.js/TS ailleurs (ex: `~/MesProjets/MonAgentJS`) :
1. Dans AgentForge, compile d'abord le SDK :
   ```bash
   cd /Users/nicolas/Documents/workspace/AgentForge/sdk-js
   npm install && npm run build
   ```
2. Dans ton projet JS externe :
   ```bash
   cd ~/MesProjets/MonAgentJS
   # Installe le SDK directement depuis le dossier local
   npm install file:/Users/nicolas/Documents/workspace/AgentForge/sdk-js
   ```
3. Tu peux maintenant importer le SDK :
   ```typescript
   import { AgentBuilder } from "@agentforge/sdk/builder";
   ```
4. Et utiliser le CLI pour push :
   ```bash
   npx agentforge push mon_fichier_agent.js
   ```

*(À l'avenir, ces SDKs seront publiés sur PyPI et npmjs pour que n'importe qui puisse faire `npm install @agentforge/sdk` ou `pip install agentforge` sans avoir le dossier en local !)*

---

## 🌐 4. Tester le Frontend (UI)

Une fois que tu as lancé `make quick-start` :
1. Ouvre ton navigateur sur **http://localhost:3000**.
2. Tu verras l'interface utilisateur d'AgentForge.
3. **À tester :**
   - Assure-toi que le frontend communique bien avec le backend (vérifie s'il n'y a pas d'erreurs CORS dans la console).
   - Les appels API du front pointent par défaut vers `NEXT_PUBLIC_API_URL=http://localhost:8000`.

---

## 🧪 5. Tester la boucle MLOps de A à Z (Backend & Auto-Finetuning)

Pour tester la puissance complète de ce que nous avons codé (le versioning, les branches, et l'auto-finetuning), voici la marche à suivre pas-à-pas :

### Étape 1 : Créer un Agent et le déployer
Utilise un de tes scripts SDK (Python ou JS) depuis n'importe quel dossier pour pusher un agent.
Exemple avec le SDK JS : `npx agentforge push mon_agent.js`

### Étape 2 : Configurer les Alias (Branches)
1. Va sur le Swagger : **http://localhost:8000/docs**
2. Connecte-toi (crée un compte + récupère le token + bouton "Authorize").
3. Trouve l'UUID de ton agent créé (via `GET /api/v1/agents`).
4. Crée un alias "production" sur la version 1 :
   - `POST /api/v1/agents/{agent_id}/aliases`
   - Body : `{"name": "production", "version_number": 1}`

### Étape 3 : Simuler une exécution excellente (Data Flywheel)
1. Lance une exécution de ton agent en visant ton alias :
   - `POST /api/v1/agents/{agent_id}/execute`
   - Body : `{"input": {"messages": [...]}, "alias": "production"}`
2. Récupère l'`execution_id` de la réponse.
3. Soumets un feedback parfait pour déclencher la sauvegarde de l'exemple pour le fine-tuning :
   - `POST /api/v1/agents/{agent_id}/executions/{execution_id}/feedback`
   - Body : `{"score": 5, "comment": "Incroyable"}`
4. *Vérification* : Si tu as un outil comme pgAdmin (ou `psql`), tu peux vérifier que la table `finetune_examples` contient bien une nouvelle ligne avec tes messages !

### Étape 4 : Déclencher le Fine-tuning Continu
1. Simule le fait que tu as assez de data, déclenche l'entraînement :
   - `POST /api/v1/finetune/trigger`
   - Body : `{"agent_id": "ton_uuid", "min_score": 4.0}`
2. Le système va compiler le JSONL, créer un `FinetuneJob` et lancer la requête vers Modal Labs.

### Étape 5 : L'Auto-Déploiement Shadow (La touche finale)
1. En temps normal, un job prend des heures. Ici, pour simuler, le système va poll le statut.
2. Une fois le job terminé (ou simulé comme "completed"), regarde les logs du backend. Tu y verras un message du type : `auto_deployed_shadow_alias`.
3. Le backend a automatiquement :
   - Créé la **Version 2** de ton agent.
   - Changé le modèle pour `provider="finetuned"`.
   - Créé ou mis à jour l'alias **"shadow"** pour qu'il pointe vers cette version 2.
4. Tu peux vérifier ça via `GET /api/v1/agents/{agent_id}/aliases`.
5. Exécute l'agent avec `"alias": "shadow"` : tu tournes désormais sur ton modèle fine-tuné personnalisé, sans avoir jamais touché manuellement au code !

---

### 🎉 Conclusion
Tu possèdes maintenant un système complet digne d'une plateforme d'IA en production, avec un SDK agnostique du dossier de travail, une gestion asynchrone par Redis, un environnement multi-branches (alias), et une boucle MLOps entièrement automatisée. Amuse-toi bien !
