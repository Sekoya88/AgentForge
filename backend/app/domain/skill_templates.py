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
]


def get_templates_by_category() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for t in SKILL_TEMPLATES:
        cat = t.get("category", "other")
        result.setdefault(cat, []).append(t)
    return result
