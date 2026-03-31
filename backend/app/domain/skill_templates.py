"""Pre-built skill templates available for one-click installation."""

from __future__ import annotations

from typing import Any

SKILL_TEMPLATES: list[dict[str, Any]] = [
    # ── Instruction skills ──────────────────────────────────────────
    {
        "name": "summarize",
        "description": "Summarise any text into concise bullet points",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "You are a summarisation expert.\n\n"
            "When the user provides text, produce a concise summary:\n"
            "1. Extract the 3-5 most important points.\n"
            "2. Present them as bullet points.\n"
            "3. Keep each bullet under 20 words.\n"
            "4. End with a one-sentence overall takeaway."
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "text",
    },
    {
        "name": "translate",
        "description": "Translate text between languages",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "You are a professional translator.\n\n"
            "When the user provides text and a target language:\n"
            "1. Detect the source language.\n"
            "2. Translate accurately, preserving tone and meaning.\n"
            "3. If the target language is not specified, translate to English.\n"
            "4. Provide the translated text only, no commentary."
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "text",
    },
    {
        "name": "code_review",
        "description": "Review code for bugs, style issues, and improvements",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "You are a senior code reviewer.\n\n"
            "When the user provides code:\n"
            "1. Check for bugs, edge cases, and security issues.\n"
            "2. Evaluate naming, structure, and readability.\n"
            "3. Suggest specific improvements with code examples.\n"
            "4. Rate severity: critical / warning / suggestion.\n"
            "5. Be constructive and concise."
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "development",
    },
    {
        "name": "data_extract",
        "description": "Extract structured data from unstructured text",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "You are a data extraction specialist.\n\n"
            "When the user provides unstructured text:\n"
            "1. Identify entities: names, dates, amounts, locations, emails, phones.\n"
            "2. Return the result as a JSON object.\n"
            "3. Use null for fields that cannot be determined.\n"
            "4. If the user specifies a schema, follow it exactly."
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "data",
    },
    {
        "name": "email_drafter",
        "description": "Draft professional emails from brief notes",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "You are a professional email writer.\n\n"
            "Given brief notes or bullet points:\n"
            "1. Draft a clear, professional email.\n"
            "2. Include subject line, greeting, body, and sign-off.\n"
            "3. Match the requested tone (formal, friendly, urgent).\n"
            "4. Keep it concise — aim for under 150 words."
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "text",
    },
    # ── Code skills ─────────────────────────────────────────────────
    {
        "name": "web_search",
        "description": "Fetch and extract text from a URL",
        "skill_type": "code",
        "source_code": (
            "import httpx\n"
            "from html.parser import HTMLParser\n"
            "\n\n"
            "class _TextExtractor(HTMLParser):\n"
            "    def __init__(self):\n"
            "        super().__init__()\n"
            "        self._parts: list[str] = []\n"
            "        self._skip = False\n"
            "    def handle_starttag(self, tag, attrs):\n"
            "        self._skip = tag in ('script', 'style')\n"
            "    def handle_endtag(self, tag):\n"
            "        if tag in ('script', 'style'):\n"
            "            self._skip = False\n"
            "    def handle_data(self, data):\n"
            "        if not self._skip:\n"
            "            self._parts.append(data.strip())\n"
            "    def text(self) -> str:\n"
            "        return ' '.join(p for p in self._parts if p)\n"
            "\n\n"
            "def run(url: str) -> str:\n"
            "    resp = httpx.get(url.strip(), timeout=10, follow_redirects=True)\n"
            "    resp.raise_for_status()\n"
            "    ext = _TextExtractor()\n"
            "    ext.feed(resp.text)\n"
            "    text = ext.text()\n"
            "    return text[:3000] if len(text) > 3000 else text\n"
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": ["network"],
        "is_public": True,
        "category": "tools",
    },
    {
        "name": "json_transform",
        "description": "Parse, query, and transform JSON data",
        "skill_type": "code",
        "source_code": (
            "import json\n"
            "\n\n"
            "def run(input_text: str) -> str:\n"
            "    lines = input_text.strip().split('\\n', 1)\n"
            "    if len(lines) < 2:\n"
            "        return json.dumps(json.loads(input_text), indent=2)\n"
            "    query, data_str = lines[0].strip(), lines[1].strip()\n"
            "    data = json.loads(data_str)\n"
            "    # Simple dot-path query: 'key.subkey.0'\n"
            "    result = data\n"
            "    for part in query.split('.'):\n"
            "        if isinstance(result, list):\n"
            "            result = result[int(part)]\n"
            "        elif isinstance(result, dict):\n"
            "            result = result[part]\n"
            "        else:\n"
            "            return f'Cannot traverse into {type(result).__name__}'\n"
            "    if isinstance(result, (dict, list)):\n"
            "        return json.dumps(result, indent=2)\n"
            "    return str(result)\n"
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "data",
    },
    {
        "name": "text_stats",
        "description": "Compute word count, sentence count, and readability stats",
        "skill_type": "code",
        "source_code": (
            "import re\n"
            "import json\n"
            "\n\n"
            "def run(text: str) -> str:\n"
            "    words = text.split()\n"
            "    sentences = [s for s in re.split(r'[.!?]+', text) if s.strip()]\n"
            "    chars = len(text)\n"
            "    avg_word_len = sum(len(w) for w in words) / max(len(words), 1)\n"
            "    avg_sentence_len = len(words) / max(len(sentences), 1)\n"
            "    return json.dumps({\n"
            "        'characters': chars,\n"
            "        'words': len(words),\n"
            "        'sentences': len(sentences),\n"
            "        'avg_word_length': round(avg_word_len, 1),\n"
            "        'avg_sentence_length': round(avg_sentence_len, 1),\n"
            "    }, indent=2)\n"
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "text",
    },
    {
        "name": "creative_writer",
        "description": "Turn a premise into vivid micro-fiction or scene beats",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "You are a fiction writer.\n\n"
            "Given a premise or keywords:\n"
            "1. Write one tight scene (under 200 words).\n"
            "2. Include sensory detail and one line of dialogue.\n"
            "3. Offer two optional directions the story could take next."
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "fun",
    },
    {
        "name": "socratic_tutor",
        "description": "Guide the user with questions instead of lecturing",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "You are a Socratic tutor.\n\n"
            "Do not give the full answer immediately.\n"
            "1. Ask a guiding question about what they already know.\n"
            "2. Based on their reply, ask one deeper question.\n"
            "3. Only then give a concise explanation (under 120 words).\n"
            "Stay encouraging and precise."
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "fun",
    },
    {
        "name": "joke_host",
        "description": "Light jokes and icebreakers — keep it workplace-safe",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "You are a friendly emcee.\n\n"
            "When asked for humor:\n"
            "1. Deliver one short joke or pun tied to the user's topic.\n"
            "2. Optionally add a one-line 'groaner' alternate.\n"
            "3. Keep content inclusive and safe for work — no slurs or targeted mockery."
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "fun",
    },
    # ── Code skills (demos, matches seed / templates) ─────────────
    {
        "name": "uppercase",
        "description": "Uppercase input text (same as seed demo skill)",
        "skill_type": "code",
        "source_code": (
            "def run(x: str) -> str:\n"
            '    """Return the input uppercased."""\n'
            "    return x.upper()\n"
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "tools",
    },
    {
        "name": "echo",
        "description": "Return the input unchanged — useful for debugging graphs",
        "skill_type": "code",
        "source_code": (
            'def run(x: str) -> str:\n    """Echo input for testing tool nodes."""\n    return x\n'
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "tools",
    },
    {
        "name": "reverse_text",
        "description": "Reverse character order of the input string",
        "skill_type": "code",
        "source_code": (
            'def run(x: str) -> str:\n    """Reverse characters in x."""\n    return x[::-1]\n'
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "tools",
    },
    {
        "name": "line_count",
        "description": "Count non-empty lines in pasted text",
        "skill_type": "code",
        "source_code": (
            "import json\n"
            "\n\n"
            "def run(text: str) -> str:\n"
            "    lines = [ln for ln in text.splitlines() if ln.strip()]\n"
            '    return json.dumps({"lines": len(lines), "chars": len(text)}, indent=2)\n'
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "data",
    },
    {
        "name": "slugify",
        "description": "Turn a phrase into a lowercase hyphenated slug",
        "skill_type": "code",
        "source_code": (
            "import re\n"
            "\n\n"
            "def run(text: str) -> str:\n"
            "    s = text.strip().lower()\n"
            "    s = re.sub(r'[^a-z0-9]+', '-', s)\n"
            "    return s.strip('-')\n"
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "data",
    },
    # ── Productivity ─────────────────────────────────────────────────
    {
        "name": "meeting_notes",
        "description": (
            "Formatte des notes de réunion brutes en compte-rendu structuré"
            " avec décisions et actions"
        ),
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "Tu es un assistant de réunion professionnel.\n\n"
            "Étant donné des notes brutes:\n"
            "1. Extraire: Date, Participants, Ordre du jour\n"
            "2. Résumer les décisions (bullet points)\n"
            "3. Lister les actions: responsable + deadline si mentionnés\n"
            "4. Format Markdown structuré avec sections ##\n"
            "5. Ton professionnel et neutre"
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "productivity",
    },
    {
        "name": "action_items",
        "description": "Extrait les tâches et actions à faire depuis un texte ou email",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "Tu es un assistant d'extraction de tâches.\n\n"
            "Depuis le texte fourni:\n"
            "1. Identifie toutes les actions (verbe d'action + objet)\n"
            "2. Pour chaque action: Quoi / Qui / Quand (si mentionné)\n"
            '3. Retourner en JSON: [{"task": str, "owner": str|null, "due": str|null}]\n'
            "4. Prioritiser: urgent > important > normal"
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "productivity",
    },
    {
        "name": "date_calculator",
        "description": "Calcule des dates relatives: dans X jours, la semaine prochaine, etc.",
        "skill_type": "code",
        "source_code": (
            "from datetime import datetime, timedelta\n"
            "import re\n"
            "import json\n"
            "\n\n"
            "def run(query: str) -> str:\n"
            "    now = datetime.utcnow()\n"
            "    q = query.lower().strip()\n"
            "    result = {}\n"
            "    if m := re.search(r'in (\\d+) days?', q):\n"
            "        d = now + timedelta(days=int(m.group(1)))\n"
            "        result['date'] = d.strftime('%Y-%m-%d')\n"
            "        result['weekday'] = d.strftime('%A')\n"
            "    elif m := re.search(r'(\\d+) days? ago', q):\n"
            "        d = now - timedelta(days=int(m.group(1)))\n"
            "        result['date'] = d.strftime('%Y-%m-%d')\n"
            "        result['weekday'] = d.strftime('%A')\n"
            "    elif 'today' in q:\n"
            "        result['date'] = now.strftime('%Y-%m-%d')\n"
            "        result['weekday'] = now.strftime('%A')\n"
            "    elif 'tomorrow' in q:\n"
            "        d = now + timedelta(days=1)\n"
            "        result['date'] = d.strftime('%Y-%m-%d')\n"
            "        result['weekday'] = d.strftime('%A')\n"
            "    else:\n"
            "        result['date'] = now.strftime('%Y-%m-%d')\n"
            "        result['note'] = f'Could not parse: {query}'\n"
            "    result['now_utc'] = now.strftime('%Y-%m-%d %H:%M UTC')\n"
            "    return json.dumps(result, indent=2)\n"
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "productivity",
    },
    # ── Development ──────────────────────────────────────────────────
    {
        "name": "pr_description",
        "description": "Génère une description de Pull Request depuis un git diff ou changelog",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "Tu es un développeur senior qui rédige des descriptions de PR.\n\n"
            "Depuis le diff ou les commits:\n"
            "1. Titre clair < 72 caractères\n"
            "2. ## Summary: 2-3 bullet points du changement principal\n"
            "3. ## Changes: liste technique détaillée\n"
            "4. ## Testing: comment tester\n"
            "5. Mentionner les breaking changes si présents"
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "development",
    },
    {
        "name": "regex_extractor",
        "description": "Applique une regex sur un texte et retourne les groupes capturés en JSON",
        "skill_type": "code",
        "source_code": (
            "import re\n"
            "import json\n"
            "\n\n"
            "def run(input_text: str) -> str:\n"
            "    lines = input_text.strip().split('\\n', 1)\n"
            "    if len(lines) < 2:\n"
            "        return json.dumps("
            "{'error': 'Format: first line = regex pattern, rest = text to search'})\n"
            "    pattern, text = lines[0].strip(), lines[1]\n"
            "    try:\n"
            "        matches = re.findall(pattern, text)\n"
            "        return json.dumps(\n"
            "            {'pattern': pattern, 'matches': matches,\n"
            "             'count': len(matches)}, indent=2)\n"
            "    except re.error as e:\n"
            "        return json.dumps({'error': f'Invalid regex: {e}'})\n"
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "development",
    },
    {
        "name": "markdown_formatter",
        "description": "Convertit du texte brut ou HTML basique en Markdown propre",
        "skill_type": "code",
        "source_code": (
            "import re\n"
            "\n\n"
            "def run(text: str) -> str:\n"
            "    text = text.replace('\\r\\n', '\\n').replace('\\r', '\\n')\n"
            "    text = re.sub(r'<br\\s*/?>', '\\n', text, flags=re.IGNORECASE)\n"
            "    text = re.sub(\n"
            "        r'<p>(.*?)</p>', r'\\1\\n\\n', text,"
            " flags=re.DOTALL | re.IGNORECASE)\n"
            "    text = re.sub(\n"
            "        r'<h([1-6])>(.*?)</h\\1>',\n"
            "        lambda m: '#' * int(m.group(1)) + ' ' + m.group(2) + '\\n',\n"
            "        text, flags=re.DOTALL | re.IGNORECASE,\n"
            "    )\n"
            "    text = re.sub(\n"
            "        r'<strong>(.*?)</strong>', r'**\\1**',"
            " text, flags=re.DOTALL | re.IGNORECASE)\n"
            "    text = re.sub(\n"
            "        r'<em>(.*?)</em>', r'*\\1*',"
            " text, flags=re.DOTALL | re.IGNORECASE)\n"
            "    text = re.sub(r'<[^>]+>', '', text)\n"
            "    text = re.sub(r'\\n{3,}', '\\n\\n', text)\n"
            "    return text.strip()\n"
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "development",
    },
    # ── Data / Analysis ──────────────────────────────────────────────
    {
        "name": "sentiment_analysis",
        "description": "Analyse le sentiment d'un texte: positif/négatif/neutre avec score 0-1",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "Tu es un expert en analyse de sentiment.\n\n"
            "Depuis le texte fourni:\n"
            "1. Sentiment global: positif / négatif / neutre / mixte\n"
            "2. Score de 0 à 1 (0=très négatif, 0.5=neutre, 1=très positif)\n"
            "3. Phrases clés qui justifient ce sentiment\n"
            '4. Retourner JSON: {"sentiment": str, "score": float, "key_phrases": [str]}\n'
            "5. Si autre langue, analyser quand même et noter la langue"
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "data",
    },
    {
        "name": "csv_analyzer",
        "description": "Analyse un CSV collé en texte: résumé des colonnes, types, stats de base",
        "skill_type": "code",
        "source_code": (
            "import csv\n"
            "import json\n"
            "import io\n"
            "\n\n"
            "def run(text: str) -> str:\n"
            "    reader = csv.DictReader(io.StringIO(text.strip()))\n"
            "    rows = list(reader)\n"
            "    if not rows:\n"
            "        return json.dumps({'error': 'No data found'})\n"
            "    columns = list(rows[0].keys())\n"
            "    stats = {}\n"
            "    for col in columns:\n"
            "        values = [r[col] for r in rows if r[col].strip()]\n"
            "        numeric = []\n"
            "        for v in values:\n"
            "            try:\n"
            "                numeric.append(float(v))\n"
            "            except ValueError:\n"
            "                pass\n"
            "        stats[col] = {\n"
            "            'count': len(values),\n"
            "            'empty': len(rows) - len(values),\n"
            "        }\n"
            "        if numeric:\n"
            "            stats[col]['min'] = round(min(numeric), 2)\n"
            "            stats[col]['max'] = round(max(numeric), 2)\n"
            "            stats[col]['avg'] = round(sum(numeric) / len(numeric), 2)\n"
            "        else:\n"
            "            unique = list(set(values))[:5]\n"
            "            stats[col]['unique_sample'] = unique\n"
            "    return json.dumps(\n"
            "        {'rows': len(rows), 'columns': columns, 'stats': stats}, indent=2)\n"
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "data",
    },
    # ── Research ─────────────────────────────────────────────────────
    {
        "name": "arxiv_search",
        "description": (
            "Recherche des articles scientifiques sur ArXiv et retourne les 5 plus pertinents"
        ),
        "skill_type": "code",
        "source_code": (
            "import httpx\n"
            "import xml.etree.ElementTree as ET\n"
            "import json\n"
            "\n\n"
            "def run(query: str) -> str:\n"
            "    url = 'http://export.arxiv.org/api/query'\n"
            "    params = {\n"
            "        'search_query': f'all:{query}', 'max_results': 5, 'sortBy': 'relevance'}\n"
            "    resp = httpx.get(url, params=params, timeout=15)\n"
            "    resp.raise_for_status()\n"
            "    ns = {'atom': 'http://www.w3.org/2005/Atom'}\n"
            "    root = ET.fromstring(resp.text)\n"
            "    results = []\n"
            "    for entry in root.findall('atom:entry', ns):\n"
            "        results.append({\n"
            "            'title': (entry.findtext('atom:title', namespaces=ns) or '').strip(),\n"
            "            'summary': (\n"
            "                entry.findtext('atom:summary', namespaces=ns) or '').strip()[:300],\n"
            "            'url': (entry.findtext('atom:id', namespaces=ns) or '').strip(),\n"
            "            'published': entry.findtext('atom:published', namespaces=ns) or '',\n"
            "        })\n"
            "    return json.dumps(results, indent=2)\n"
        ),
        "instructions": None,
        "parameters_schema": {},
        "permissions": ["network"],
        "is_public": True,
        "category": "research",
    },
    # ── Text ─────────────────────────────────────────────────────────
    {
        "name": "tone_rewriter",
        "description": "Réécrit un texte dans un ton différent: formel, casual, persuasif, etc.",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "Tu es un expert en communication écrite.\n\n"
            "Quand l'utilisateur fournit un texte et un ton cible:\n"
            "1. Tons disponibles: formel, casual, persuasif, empathique, direct, inspirant\n"
            "2. Réécrire en préservant le sens exact\n"
            "3. Adapter le vocabulaire, la longueur des phrases et la structure\n"
            "4. Présenter: [Ton original] et [Ton réécrit]\n"
            "5. Si le ton n'est pas précisé, demander"
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "text",
    },
    {
        "name": "grammar_fixer",
        "description": (
            "Corrige la grammaire, l'orthographe et la ponctuation sans changer le style"
        ),
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "Tu es un correcteur linguistique professionnel.\n\n"
            "Règles strictes:\n"
            "1. Corriger UNIQUEMENT fautes de grammaire, orthographe, ponctuation\n"
            "2. Ne PAS réécrire, ne PAS changer le style ou le vocabulaire\n"
            "3. Retourner le texte corrigé puis une liste des corrections: [original] → [corrigé]\n"
            "4. Si le texte est déjà correct, dire 'Aucune correction nécessaire'\n"
            "5. Respecter la langue du texte (fr/en/autre)"
        ),
        "parameters_schema": {},
        "permissions": [],
        "is_public": True,
        "category": "text",
    },
    # ── Google (require OAuth) ────────────────────────────────────────
    {
        "name": "gmail_reader",
        "description": "Lit les derniers emails Gmail de l'utilisateur et les résume",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "Tu as accès aux emails Gmail via l'outil read_gmail.\n\n"
            "Quand l'utilisateur demande ses emails:\n"
            "1. Appeler read_gmail (défaut: 10 derniers)\n"
            "2. Présenter: De / Date / Sujet / Résumé 2 lignes\n"
            "3. Si l'utilisateur veut lire un email complet, l'afficher\n"
            "4. Proposer des actions: répondre, archiver, transférer"
        ),
        "parameters_schema": {},
        "permissions": ["google_gmail"],
        "is_public": False,
        "category": "google",
    },
    {
        "name": "calendar_assistant",
        "description": "Consulte et gère le calendrier Google de l'utilisateur",
        "skill_type": "instruction",
        "source_code": "",
        "instructions": (
            "Tu gères le Google Calendar de l'utilisateur"
            " via read_calendar et create_calendar_event.\n\n"
            "Pour consulter l'agenda:\n"
            "1. Appeler read_calendar avec la plage de dates\n"
            "2. Présenter: Heure / Titre / Lieu / Participants\n"
            "3. Signaler les conflits\n\n"
            "Pour créer un événement:\n"
            "1. Collecter: titre, début, fin, participants (optionnel)\n"
            "2. Vérifier la disponibilité\n"
            "3. Demander confirmation avant de créer\n"
            "4. Confirmer avec lien vers l'événement"
        ),
        "parameters_schema": {},
        "permissions": ["google_calendar"],
        "is_public": False,
        "category": "google",
    },
]


def get_templates_by_category() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for t in SKILL_TEMPLATES:
        cat = t.get("category", "other")
        result.setdefault(cat, []).append(t)
    return result
