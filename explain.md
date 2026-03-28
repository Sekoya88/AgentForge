# AgentForge — Guide de test complet

> Un guide orienté **cas d'usage concret**, pas "la page s'affiche". Chaque étape valide une chaîne complète : API → DB → orchestrateur → UI.

---

## Démarrage

### Tout en Docker (recommandé — logs backend inclus)

```bash
# Démarrer tous les services : backend + frontend + db + redis
docker compose up --build

# Migrations BDD (1 seule fois, ou après chaque alembic revision)
docker compose exec backend alembic upgrade head

# Vérifier que tout tourne
curl http://localhost:8000/health
# → {"status":"ok","checks":{"db":"ok","redis":"ok"}}
```

**Voir les logs backend en temps réel :**
```bash
docker compose logs -f backend          # backend seul (hot-reload uvicorn)
docker compose logs -f                  # tous les services
docker compose logs --tail=100 -f backend  # 100 dernières lignes + suivi
```

Les logs sont **JSON structuré** (niveau, path, status, duration, correlation-id). Pour filtrer les erreurs :
```bash
docker compose logs -f backend 2>&1 | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        if d.get('level') in ('ERROR','WARNING'): print(line, end='')
    except: pass
"
```

Autres commandes utiles :
```bash
docker compose exec backend bash            # shell dans le container
docker compose exec backend alembic current # version DB courante
docker compose restart backend              # redémarrer sans tout couper
```

### Dev local (sans Docker, hot-reload plus rapide)

```bash
docker compose up -d db redis          # infra seulement
cd backend && alembic upgrade head && uvicorn app.main:app --reload
cd frontend && npm run dev
```

**`.env` minimal** (copier `.env.example`) :
```
JWT_SECRET_KEY=changez-moi-min-32-caracteres
OPENAI_API_KEY=sk-...         # pour les nœuds LLM réels
REDIS_URL=redis://localhost:6380/0
DATABASE_URL=postgresql+asyncpg://forge:forge@localhost:5433/agentforge
```

---

## Cas d'usage complet : Support Ticket Triage Bot

Un seul agent pour valider **toutes les features** : LLM node, tool node, routing conditionnel, skill, HITL, ExecutionPolicy, SSE streaming, export, eval CLI, version history, red-team.

```
[ticket utilisateur]
        │
        ▼
┌──────────────┐
│  classify    │  LLM — répond exactement "urgent" ou "normal"
└──────┬───────┘
       │ condition: "urgent"         │ condition_type: "always"
       ▼                             ▼
┌──────────────┐             ┌──────────────┐
│   escalate   │             │   respond    │
│  (tool node) │             │  (LLM node)  │
│ HITL requis  │──────────── │  Rédige la   │
│ avant envoi  │  always     │  réponse     │
└──────────────┘             └──────────────┘
```

---

### 1) Auth — obtenir un token

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@test.com","password":"Test1234!","display_name":"Dev"}'

TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@test.com","password":"Test1234!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

Sur le **frontend** : Register → Login → vérifier que l'avatar "Dev" est affiché (pas de "Login" fantôme après refresh).

---

### 2) Créer le skill `notify_team`

Un skill = une fonction Python `run(input: str) -> str` stockée dans le registry.

**Via curl :**
```bash
SKILL_ID=$(curl -s -X POST http://localhost:8000/api/v1/skills \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "notify_team",
    "description": "Alerte immédiate à léquipe on-call",
    "skill_type": "code",
    "source_code": "def run(input: str) -> str:\n    # En prod : appel PagerDuty, Slack, etc.\n    return f\"[ALERTE ENVOYEE] {input[:120]}\""
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Skill: $SKILL_ID"
```

**Via frontend** : Skills → New Skill → remplir le formulaire → Save → le badge "✓ valid" doit apparaître.

> **Valider le code statiquement :**
> `curl -X POST .../skills/$SKILL_ID/validate -H "Authorization: Bearer $TOKEN"`

---

### 3) Créer l'agent

```bash
AGENT_ID=$(curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Triage Bot\",
    \"description\": \"Classe les tickets et escalade les urgences\",
    \"graph_definition\": {
      \"nodes\": [
        {
          \"id\": \"classify\",
          \"type\": \"llm\",
          \"config\": {\"prompt\": \"Tu es un classificateur de tickets support. Réponds uniquement par un seul mot : 'urgent' si le ticket décrit une panne, perte de données ou incident de sécurité en production. Sinon réponds 'normal'.\"}
        },
        {
          \"id\": \"escalate\",
          \"type\": \"tool\",
          \"config\": {\"tool_name\": \"notify_team\"}
        },
        {
          \"id\": \"respond\",
          \"type\": \"llm\",
          \"config\": {\"prompt\": \"Tu es un agent de support. Rédige une réponse professionnelle et empathique en 3-4 phrases maximum.\"}
        }
      ],
      \"edges\": [
        {\"from\": \"classify\", \"to\": \"escalate\", \"condition\": \"urgent\",  \"condition_type\": \"contains\"},
        {\"from\": \"classify\", \"to\": \"respond\",  \"condition_type\": \"always\"},
        {\"from\": \"escalate\", \"to\": \"respond\",  \"condition_type\": \"always\"}
      ],
      \"entry_point\": \"classify\"
    },
    \"model_config\": {\"provider\": \"openai\", \"model\": \"gpt-4o-mini\", \"temperature\": 0.1},
    \"execution_policy\": {
      \"allowed_tools\": [\"notify_team\"],
      \"require_human_approval_for\": [\"notify_team\"],
      \"deny_patterns\": [\"password\", \"Bearer\\\\s+\\\\S+\"],
      \"max_graph_steps\": 20
    },
    \"skills\": [\"$SKILL_ID\"]
  }" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Agent: $AGENT_ID"
```

> **Sans clé OpenAI** : remplacer `"provider":"openai"` par `"provider":"mock"`. Le routing ne fonctionnera pas (le mock ne dit jamais "urgent") mais toutes les autres features (SSE, versions, export…) marchent.

---

### 4) Exécuter et observer le HITL

#### Démarrer l'exécution async

```bash
EXEC_ID=$(curl -s -X POST "http://localhost:8000/api/v1/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input_messages":[{"role":"user","content":"URGENT : toute la prod est HS, base de données inaccessible"}],"run_async":true}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

#### Suivre le stream SSE (dans un 2ème terminal)

```bash
curl -N "http://localhost:8000/api/v1/agents/$AGENT_ID/stream/$EXEC_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Tu verras défiler :
```
event: agent_start
data: {"agent_name":"classify","node_type":"llm",...}

event: agent_end
data: {"agent_name":"classify","output_preview":"urgent",...}

event: interrupt
data: {"node_id":"escalate","interrupt_state":{"pending_tools":[{"tool_name":"notify_team","arg":"..."}]}}

(stream en pause — attend ta décision)
```

#### Approuver l'action

```bash
curl -s -X POST "http://localhost:8000/api/v1/agents/$AGENT_ID/executions/$EXEC_ID/interrupt" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decisions":[{"tool_name":"notify_team","decision":"approve"}]}'
```

Ou **rejeter** : `"decision":"reject"` → l'escalade est annulée, l'exécution continue vers `respond`.

#### Lire le résultat final

```bash
curl -s "http://localhost:8000/api/v1/agents/$AGENT_ID/executions/$EXEC_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], d['output_messages'][-1]['content'])"
```

**Via frontend** : page agent → message → Execute → la **modal HITL** apparaît automatiquement → Approve / Reject → le stream reprend.

#### Voir les logs Docker pendant l'exécution

```bash
# Dans un 3ème terminal, pendant que l'exécution tourne
docker compose logs -f backend
```
Tu verras les requêtes POST /execute, GET /stream, POST /interrupt avec status codes et durées.

---

### 5) Tester la deny_pattern (sécurité)

La politique `deny_patterns` bloque les inputs qui contiennent des secrets.

```bash
# Ce message contient "password" → doit être bloqué par l'orchestrateur
curl -s -X POST "http://localhost:8000/api/v1/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input_messages":[{"role":"user","content":"Mon password123 ne fonctionne plus"}],"run_async":false}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], d.get('output_messages',[][-1:]))"
```

Le tool node `escalate` sera bloqué si le contenu du ticket contient un pattern interdit. La réponse contiendra un message d'erreur de policy.

---

### 6) Export + test local (SDK)

```bash
# Export avec le source code du skill embarqué + hash SHA256
curl -s "http://localhost:8000/api/v1/agents/$AGENT_ID/export?include_skills=true" \
  -H "Authorization: Bearer $TOKEN" \
  -o triage_bot.json

# Voir la structure
python3 -c "import json; d=json.load(open('triage_bot.json')); print(list(d.keys()))"
# ['name', 'description', 'graph_definition', 'model_config', 'execution_policy', 'skills', 'version']

# Le skill a un sha256 pour vérification d'intégrité
python3 -c "import json; d=json.load(open('triage_bot.json')); print(d['skills'][0].get('sha256','no hash'))"
```

```bash
pip install agentforge-sdk   # ou: pip install ./sdk

# Valider le graphe sans serveur
agentforge validate triage_bot.json
# → ok: graph_definition is valid

# Exécuter localement
agentforge run triage_bot.json -m "Impossible de me connecter à mon compte"
agentforge run triage_bot.json -m "URGENT : prod DB down, toutes les APIs KO"
```

---

### 7) Batch eval en CI

Créer `tests/triage_eval.jsonl` :
```jsonl
{"input": "Je narrive pas à me connecter", "expected": "compte"}
{"input": "Comment exporter mes données ?", "expected": "export"}
{"input": "URGENT : base de données hors ligne", "expected": "ALERTE"}
{"input": "Question sur ma facture du mois dernier", "expected": "facture"}
{"input": "Tous nos serveurs sont tombés", "expected": "tombés"}
```

```bash
agentforge eval triage_bot.json tests/triage_eval.jsonl --output results.json
# Passed: 4/5 (80.0%)   ← exit 0 si ≥70%

# Détail par cas
python3 -c "
import json
for r in json.load(open('results.json')):
    mark = '✓' if r['passed'] else '✗'
    print(f\"{mark} [{r['input'][:40]}] → {r['output'][:50]}\")
"
```

**Intégration CI :**
```yaml
- name: Pull + test agent
  run: |
    agentforge pull $AGENT_ID --version 3 -o triage_bot.json  # version pinée
    agentforge validate triage_bot.json
    agentforge eval triage_bot.json tests/triage_eval.jsonl
  env:
    AGENTFORGE_TOKEN: ${{ secrets.AGENTFORGE_TOKEN }}
    AGENTFORGE_API_URL: ${{ vars.AGENTFORGE_URL }}
```

---

### 8) Version history, diff et rollback

Chaque `PUT /agents/{id}` crée un snapshot automatique.

```bash
# Modifier l'agent (ex: changer le prompt du nœud classify)
curl -s -X PUT "http://localhost:8000/api/v1/agents/$AGENT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Triage Bot v2"}'

# Lister les versions
curl -s "http://localhost:8000/api/v1/agents/$AGENT_ID/versions" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; [print(f'v{v[\"version_number\"]} {v[\"change_note\"]} {v[\"created_at\"]}') for v in json.load(sys.stdin)]"

# Diff v1 → v2
curl -s "http://localhost:8000/api/v1/agents/$AGENT_ID/versions/diff?from=1&to=2" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Rollback à v1
curl -s -X POST "http://localhost:8000/api/v1/agents/$AGENT_ID/rollback/1" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; print('Rollback ok, name=', json.load(sys.stdin)['name'])"

# Stats d'exécution par version (connectées à la table du frontend)
curl -s "http://localhost:8000/api/v1/agents/$AGENT_ID/stats/versions" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
```

**Via frontend** : section "Version history" → expand → voir graph_definition · bouton "Rollback" · section "Execution stats by version" (tableau pass-rate + latence).

---

### 9) Red-team

```bash
CAMPAIGN=$(curl -s -X POST http://localhost:8000/api/v1/campaigns \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"name\": \"Triage Bot Security\",
    \"test_types\": [\"prompt_injection\",\"jailbreak\",\"sensitive_data\",\"system_prompt_override\",\"rbac\"],
    \"max_prompts_per_type\": 3
  }")

CAMPAIGN_ID=$(echo "$CAMPAIGN" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Campaign: $CAMPAIGN_ID | Score: $(echo $CAMPAIGN | python3 -c \"import sys,json; print(json.load(sys.stdin).get('security_score','pending'))\")"

# Rapport
curl -s "http://localhost:8000/api/v1/campaigns/$CAMPAIGN_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Score: {d.get('security_score')} | {d.get('passed_tests')}/{d.get('total_tests')} tests passed\")"
```

> **`REDTEAM_MODE=mock`** (défaut) : score et rapport structurés, tests synthétiques — bon pour CI et régression UI, pas pour audit sécu réel. Pour une valeur sécu réelle : `REDTEAM_MODE=promptfoo` + `OPENAI_API_KEY`.

**Via frontend** : page agent → "Run red-team" → voir le score mis à jour sur la fiche + historique des campagnes.

---

## Autres parcours à valider

### RAG (Knowledge → retrieve → réponse)

1. **Knowledge** : indexer un texte avec un code unique fictif (`AF-TEST-7741`)
2. Créer un agent avec un nœud **tool** `"tool_name": "retrieve"` comme entry_point
3. Exécuter avec une question qui requiert `AF-TEST-7741`
4. **Succès** : la réponse contient le terme indexé

**Échecs typiques** : clé OpenAI manquante (pour les embeddings), 0 chunks indexés, `tool_name` ≠ `retrieve`.

### Builder graphe

1. **Open builder** depuis la fiche agent → déplacer un nœud / changer une condition d'edge → **Save**
2. Recharger la page → la définition est persistée → **Execute** un message minimal pour vérifier que le nouveau routing fonctionne

### Sandbox (code arbitraire)

```bash
curl -s -X POST http://localhost:8000/api/v1/sandbox/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"code":"result = sum(range(100))\nprint(result)","run_async":false}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('exit:', d['exit_code'], 'stdout:', d['stdout'])"
# exit: 0  stdout: 4950
```

---

## Ce qui ne prouve rien seul

| Ce qu'on voit | Ce que ça ne valide pas |
|---|---|
| Page Agents qui charge | Exécution réelle de l'orchestrateur |
| Job Finetune "pending" | Entraînement GPU (pas branché sans Modal) |
| Score red-team en mode mock | Résistance réelle du prompt aux attaques |
| Sandbox isolé | Intégration complète skill → agent → politique |

---

## Troubleshooting rapide

| Symptôme | Cause | Fix |
|---|---|---|
| `{"status":"degraded","checks":{"db":"error"}}` | Postgres non démarré | `docker compose up -d db` |
| `{"checks":{"redis":"unavailable"}}` | Redis manquant (async désactivé silencieusement) | `docker compose up -d redis` |
| `422 Unprocessable Entity` sur /execute | `input_messages` malformé | Vérifier `[{"role":"user","content":"..."}]` |
| SSE ne se termine pas | Exécution bloquée en HITL | POST `.../interrupt` avec decisions |
| `Input blocked by deny_pattern` | Message matche un pattern interdit | Vérifier `execution_policy.deny_patterns` |
| `RuntimeError: MODAL_INFERENCE_URL not set` | Provider `finetuned` sans Modal | Utiliser `provider: openai` |
| Frontend vide après login | `NEXT_PUBLIC_API_URL` mal configuré | `.env` → `http://localhost:8000` |
| `tool notify_team not found` | Skill non attachée à l'agent | Vérifier `skills: ["$SKILL_ID"]` dans le PUT |

---

## Récap des features couvertes

| Feature | Où tester |
|---|---|
| Auth JWT + session | Étape 1 |
| Skill registry + validation | Étape 2 |
| LLM node + routing conditionnel | Étape 3 |
| HITL (require_human_approval_for) | Étape 4 |
| deny_patterns (sécurité input) | Étape 5 |
| Export JSON + SHA256 skill | Étape 6 |
| `agentforge validate / run / eval` | Étapes 6-7 |
| Version history, diff, rollback | Étape 8 |
| Red-team campaign | Étape 9 |
| RAG / Knowledge | Section dédiée |
| SSE streaming | Étape 4 |
| Docker logs | Démarrage |
