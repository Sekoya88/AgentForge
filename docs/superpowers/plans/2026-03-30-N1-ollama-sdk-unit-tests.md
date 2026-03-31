# Phase N1 — Ollama Provider + SDK Unit Tests

> **Statut : terminé** (implémenté en codebase : `ollama` dans `llm_invoke`, factory côté SDK, tests unitaires Py + Vitest JS). Ce fichier reste la référence d’architecture ; les cases à cocher peuvent être marquées manuellement si besoin d’audit.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter Ollama comme provider LLM dans le SDK Python et le backend, et créer une suite de tests unitaires complète pour le SDK Python et TypeScript.

**Architecture:** On extrait la factory LLM du `if/elif` inline en un module `llm_factory.py` dans le SDK. L'`agent.py` devient un consommateur de cette factory. Le backend `llm_invoke.py` reçoit un cas `ollama` indépendant. Les tests unitaires couvrent le builder, les types, la policy, la validation de graphe, l'AFG YAML et la factory — tous sans appel réseau.

**Tech Stack:** Python 3.11+, pytest, unittest.mock, langchain-ollama, Vitest (TypeScript), uv (gestionnaire de dépendances)

---

## Fichiers touchés

| Fichier | Action |
|---------|--------|
| `sdk/pyproject.toml` | Modifier — ajouter `langchain-ollama` + `pytest` dev deps |
| `sdk/pytest.ini` | Créer — config pytest avec marker `integration` |
| `sdk/src/agentforge/types.py` | Modifier — `AgentModelConfig` + `base_url` + `options` |
| `sdk/src/agentforge/llm_factory.py` | Créer — `build_llm()` factory |
| `sdk/src/agentforge/agent.py` | Modifier — utilise `llm_factory.build_llm()` |
| `sdk/src/agentforge/builder.py` | Modifier — `.model()` accepte `base_url` et `options` |
| `sdk/src/agentforge/__init__.py` | Modifier — exporte `build_llm` |
| `sdk/tests/__init__.py` | Créer — vide |
| `sdk/tests/unit/__init__.py` | Créer — vide |
| `sdk/tests/unit/test_types.py` | Créer — tests Pydantic |
| `sdk/tests/unit/test_llm_factory.py` | Créer — tests factory (tout mocké) |
| `sdk/tests/unit/test_builder.py` | Créer — tests fluent API |
| `sdk/tests/unit/test_policy.py` | Créer — tests AgentPolicy |
| `sdk/tests/unit/test_graph_validate.py` | Créer — tests validation graphe |
| `sdk/tests/unit/test_afg_yaml.py` | Créer — tests round-trip YAML |
| `backend/pyproject.toml` | Modifier — ajouter `langchain-ollama` |
| `backend/app/infrastructure/orchestration/llm_invoke.py` | Modifier — ajouter cas `ollama` |
| `sdk-js/package.json` | Modifier — ajouter vitest |
| `sdk-js/vitest.config.ts` | Créer |
| `sdk-js/src/__tests__/builder.test.ts` | Créer |
| `sdk-js/src/__tests__/types.test.ts` | Créer |
| `sdk-js/src/__tests__/client.test.ts` | Créer |

---

## Task 1 : Infrastructure de test SDK Python

**Files:**
- Modify: `sdk/pyproject.toml`
- Create: `sdk/pytest.ini`
- Create: `sdk/tests/__init__.py`
- Create: `sdk/tests/unit/__init__.py`

- [ ] **Step 1 : Mettre à jour pyproject.toml**

Remplacer la section `[project]` de `sdk/pyproject.toml` par :

```toml
[project]
name = "agentforge"
version = "0.1.0"
description = "AgentForge SDK for loading and running agents locally."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "langchain>=0.3",
    "langgraph>=0.2",
    "langchain-openai",
    "langchain-google-genai",
    "langchain-ollama>=0.3.0",
    "pydantic",
    "pyyaml>=6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2 : Créer pytest.ini**

```ini
# sdk/pytest.ini
[pytest]
asyncio_mode = auto
markers =
    integration: requires Ollama running locally (deselect with '-m "not integration"')
```

- [ ] **Step 3 : Créer les fichiers __init__.py**

```bash
touch sdk/tests/__init__.py sdk/tests/unit/__init__.py
```

- [ ] **Step 4 : Installer les dépendances de dev**

```bash
cd sdk && pip install -e ".[dev]"
```

Expected : installation sans erreur, `pytest` disponible.

- [ ] **Step 5 : Vérifier que pytest tourne**

```bash
cd sdk && pytest tests/ -v
```

Expected : `no tests ran` (0 collected), pas d'erreur.

- [ ] **Step 6 : Commit**

```bash
git add sdk/pyproject.toml sdk/pytest.ini sdk/tests/__init__.py sdk/tests/unit/__init__.py
git commit -m "test(sdk): scaffold test infrastructure with pytest and integration marker"
```

---

## Task 2 : Tests types + extension AgentModelConfig

**Files:**
- Create: `sdk/tests/unit/test_types.py`
- Modify: `sdk/src/agentforge/types.py`

- [ ] **Step 1 : Écrire les tests (failing)**

Créer `sdk/tests/unit/test_types.py` :

```python
import pytest
from pydantic import ValidationError
from agentforge.types import (
    AgentModelConfig,
    NodeConfig,
    EdgeConfig,
    GraphDefinition,
    PolicyConfig,
    SkillSpec,
    AgentDefinition,
)


class TestAgentModelConfig:
    def test_defaults(self):
        cfg = AgentModelConfig()
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4o"
        assert cfg.temperature == 0.7
        assert cfg.base_url is None
        assert cfg.options == {}

    def test_ollama_config(self):
        cfg = AgentModelConfig(
            provider="ollama",
            model="llama3.2",
            base_url="http://localhost:11434",
            options={"num_ctx": 4096},
        )
        assert cfg.provider == "ollama"
        assert cfg.base_url == "http://localhost:11434"
        assert cfg.options["num_ctx"] == 4096

    def test_options_defaults_to_empty_dict(self):
        cfg = AgentModelConfig(provider="openai", model="gpt-4o", temperature=0.5)
        assert cfg.options == {}

    def test_temperature_range(self):
        cfg = AgentModelConfig(temperature=0.0)
        assert cfg.temperature == 0.0
        cfg2 = AgentModelConfig(temperature=2.0)
        assert cfg2.temperature == 2.0


class TestNodeConfig:
    def test_valid_node(self):
        n = NodeConfig(id="step1", type="llm", config={"system_prompt": "hello"})
        assert n.id == "step1"
        assert n.type == "llm"

    def test_id_min_length(self):
        with pytest.raises(ValidationError):
            NodeConfig(id="", type="llm", config={})

    def test_id_max_length(self):
        with pytest.raises(ValidationError):
            NodeConfig(id="x" * 129, type="llm", config={})

    def test_default_type(self):
        n = NodeConfig(id="n1", config={})
        assert n.type == "llm"

    def test_custom_type_allowed(self):
        n = NodeConfig(id="n1", type="my_custom_node", config={})
        assert n.type == "my_custom_node"


class TestEdgeConfig:
    def test_from_alias(self):
        e = EdgeConfig(**{"from": "a", "to": "b"})
        assert e.from_ == "a"
        assert e.to == "b"

    def test_from_field_name(self):
        e = EdgeConfig(from_="a", to="b")
        assert e.from_ == "a"

    def test_condition_type_default(self):
        e = EdgeConfig(from_="a", to="b")
        assert e.condition_type == "always"

    def test_invalid_condition_type(self):
        with pytest.raises(ValidationError):
            EdgeConfig(**{"from": "a", "to": "b", "condition_type": "unknown"})


class TestPolicyConfig:
    def test_defaults(self):
        p = PolicyConfig()
        assert p.allowed_tools is None
        assert p.denied_tools == []
        assert p.max_cost_usd is None
        assert p.max_graph_steps is None

    def test_set_values(self):
        p = PolicyConfig(max_cost_usd=0.5, max_graph_steps=10, denied_tools=["exec"])
        assert p.max_cost_usd == 0.5
        assert p.max_graph_steps == 10
        assert "exec" in p.denied_tools


class TestSkillSpec:
    def test_instruction_skill(self):
        s = SkillSpec(name="summarizer", skill_type="instruction", instructions="Summarize text")
        assert s.skill_type == "instruction"
        assert s.source_code is None

    def test_code_skill(self):
        s = SkillSpec(name="calc", skill_type="code", source_code="def run(x): return x")
        assert s.skill_type == "code"

    def test_invalid_skill_type(self):
        with pytest.raises(ValidationError):
            SkillSpec(name="bad", skill_type="unknown")


class TestAgentDefinition:
    def test_model_config_alias(self):
        from agentforge.types import GraphDefinition
        gd = GraphDefinition(
            nodes=[NodeConfig(id="n1", type="llm", config={})],
            edges=[],
            entry_point="n1",
        )
        ad = AgentDefinition(
            name="test",
            graph_definition=gd,
            model_config=AgentModelConfig(),
        )
        dumped = ad.model_dump(by_alias=True)
        assert "model_config" in dumped
```

- [ ] **Step 2 : Lancer les tests → ils échouent**

```bash
cd sdk && pytest tests/unit/test_types.py -v
```

Expected : FAILED sur `test_defaults` et `test_ollama_config` → `AgentModelConfig` n'a pas encore `base_url` ni `options`.

- [ ] **Step 3 : Modifier AgentModelConfig dans types.py**

Dans `sdk/src/agentforge/types.py`, remplacer la classe `AgentModelConfig` :

```python
class AgentModelConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o"
    temperature: float = 0.7
    base_url: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4 : Lancer les tests → ils passent**

```bash
cd sdk && pytest tests/unit/test_types.py -v
```

Expected : tous PASSED.

- [ ] **Step 5 : Commit**

```bash
git add sdk/src/agentforge/types.py sdk/tests/unit/test_types.py
git commit -m "feat(sdk): extend AgentModelConfig with base_url and options fields"
```

---

## Task 3 : llm_factory.py SDK + tests

**Files:**
- Create: `sdk/src/agentforge/llm_factory.py`
- Create: `sdk/tests/unit/test_llm_factory.py`

- [ ] **Step 1 : Écrire les tests (failing)**

Créer `sdk/tests/unit/test_llm_factory.py` :

```python
from unittest.mock import MagicMock, patch
import pytest
from agentforge.llm_factory import build_llm


class TestBuildLlm:
    @patch("agentforge.llm_factory.ChatOpenAI")
    def test_openai_provider(self, MockOpenAI):
        mock_instance = MagicMock()
        MockOpenAI.return_value = mock_instance
        result = build_llm(provider="openai", model="gpt-4o", temperature=0.5)
        MockOpenAI.assert_called_once_with(model="gpt-4o", temperature=0.5)
        assert result is mock_instance

    @patch("agentforge.llm_factory.ChatGoogleGenerativeAI")
    def test_google_provider(self, MockGoogle):
        mock_instance = MagicMock()
        MockGoogle.return_value = mock_instance
        result = build_llm(provider="google", model="gemini-2.5-flash", temperature=0.3)
        MockGoogle.assert_called_once_with(model="gemini-2.5-flash", temperature=0.3)
        assert result is mock_instance

    @patch("agentforge.llm_factory.ChatGoogleGenerativeAI")
    def test_gemini_alias(self, MockGoogle):
        mock_instance = MagicMock()
        MockGoogle.return_value = mock_instance
        result = build_llm(provider="gemini", model="gemini-2.5-flash", temperature=0.3)
        MockGoogle.assert_called_once()
        assert result is mock_instance

    @patch("agentforge.llm_factory.ChatOllama")
    def test_ollama_provider_defaults(self, MockOllama):
        mock_instance = MagicMock()
        MockOllama.return_value = mock_instance
        result = build_llm(provider="ollama", model="llama3.2", temperature=0.7)
        MockOllama.assert_called_once_with(
            model="llama3.2",
            temperature=0.7,
            base_url="http://localhost:11434",
        )
        assert result is mock_instance

    @patch("agentforge.llm_factory.ChatOllama")
    def test_ollama_provider_custom_base_url(self, MockOllama):
        mock_instance = MagicMock()
        MockOllama.return_value = mock_instance
        build_llm(
            provider="ollama",
            model="mistral",
            temperature=0.5,
            base_url="http://remote:11434",
        )
        MockOllama.assert_called_once_with(
            model="mistral",
            temperature=0.5,
            base_url="http://remote:11434",
        )

    @patch("agentforge.llm_factory.ChatOllama")
    def test_ollama_provider_with_options(self, MockOllama):
        mock_instance = MagicMock()
        MockOllama.return_value = mock_instance
        build_llm(
            provider="ollama",
            model="llama3.2",
            temperature=0.7,
            options={"num_ctx": 4096},
        )
        call_kwargs = MockOllama.call_args[1]
        assert call_kwargs.get("num_ctx") == 4096

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            build_llm(provider="unknown_xyz", model="foo", temperature=0.5)
```

- [ ] **Step 2 : Lancer les tests → ils échouent**

```bash
cd sdk && pytest tests/unit/test_llm_factory.py -v
```

Expected : FAILED — `ModuleNotFoundError: No module named 'agentforge.llm_factory'`

- [ ] **Step 3 : Créer sdk/src/agentforge/llm_factory.py**

```python
"""Lightweight LLM factory for the AgentForge SDK (no backend infra dependencies)."""

from typing import Any


def build_llm(
    provider: str,
    model: str,
    temperature: float = 0.7,
    base_url: str | None = None,
    options: dict[str, Any] | None = None,
):
    """Return an instantiated LangChain chat model for the given provider.

    Raises ValueError for unknown providers.
    No network call is made at construction time.
    """
    provider = provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=temperature)

    if provider in ("google", "gemini"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, temperature=temperature)

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        kwargs: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "base_url": base_url or "http://localhost:11434",
        }
        if options:
            kwargs.update(options)
        return ChatOllama(**kwargs)

    raise ValueError(
        f"Unknown provider: {provider!r}. "
        "Supported: openai, google, gemini, ollama"
    )
```

- [ ] **Step 4 : Lancer les tests → ils passent**

```bash
cd sdk && pytest tests/unit/test_llm_factory.py -v
```

Expected : tous PASSED.

- [ ] **Step 5 : Exporter depuis __init__.py**

Dans `sdk/src/agentforge/__init__.py`, ajouter `build_llm` :

```python
from .agent import LocalAgent, load_agent, node
from .afg_yaml import compile_afg_yaml_to_export, load_afg_yaml
from .builder import Agent, AgentPolicy
from .llm_factory import build_llm
from .types import AgentDefinition, NodeConfig, PolicyConfig, SkillSpec

__all__ = [
    "load_agent",
    "node",
    "LocalAgent",
    "Agent",
    "AgentPolicy",
    "AgentDefinition",
    "NodeConfig",
    "SkillSpec",
    "PolicyConfig",
    "load_afg_yaml",
    "compile_afg_yaml_to_export",
    "build_llm",
]
```

- [ ] **Step 6 : Commit**

```bash
git add sdk/src/agentforge/llm_factory.py sdk/src/agentforge/__init__.py sdk/tests/unit/test_llm_factory.py
git commit -m "feat(sdk): add llm_factory with ollama support"
```

---

## Task 4 : Refactor agent.py pour utiliser llm_factory

**Files:**
- Modify: `sdk/src/agentforge/agent.py`

- [ ] **Step 1 : Modifier `_create_step_function` dans agent.py**

Localiser le bloc `if node_type == "llm":` dans `sdk/src/agentforge/agent.py` (autour de la ligne 114).

Remplacer ce bloc :

```python
if node_type == "llm":
    from langchain_openai import ChatOpenAI
    from langchain_google_genai import ChatGoogleGenerativeAI

    provider = self.model_config.get("provider", "openai")
    model_name = self.model_config.get("model", "gpt-4o")
    temperature = self.model_config.get("temperature", 0.7)
    sys_prompt = config.get("system_prompt", "")

    lc_messages = []
    if sys_prompt:
        lc_messages.append(SystemMessage(content=sys_prompt))
    lc_messages.extend(messages)

    if provider == "openai":
        llm = ChatOpenAI(model=model_name, temperature=temperature)
    elif provider in ("google", "gemini"):
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
    else:
        llm = ChatOpenAI(model="gpt-4o", temperature=temperature)

    res = await llm.ainvoke(lc_messages)
    return {"messages": [res]}
```

Par :

```python
if node_type == "llm":
    from agentforge.llm_factory import build_llm

    provider = self.model_config.get("provider", "openai")
    model_name = self.model_config.get("model", "gpt-4o")
    temperature = float(self.model_config.get("temperature", 0.7))
    base_url = self.model_config.get("base_url")
    options = self.model_config.get("options") or {}
    sys_prompt = config.get("system_prompt", "")

    lc_messages = []
    if sys_prompt:
        lc_messages.append(SystemMessage(content=sys_prompt))
    lc_messages.extend(messages)

    try:
        llm = build_llm(
            provider=provider,
            model=model_name,
            temperature=temperature,
            base_url=base_url,
            options=options,
        )
    except ValueError:
        # Fallback gracieux pour providers non supportés
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o", temperature=temperature)

    res = await llm.ainvoke(lc_messages)
    return {"messages": [res]}
```

- [ ] **Step 2 : Vérifier que les tests existants passent toujours**

```bash
cd sdk && pytest tests/unit/ -v
```

Expected : tous PASSED.

- [ ] **Step 3 : Commit**

```bash
git add sdk/src/agentforge/agent.py
git commit -m "refactor(sdk): agent.py uses llm_factory instead of inline provider if/elif"
```

---

## Task 5 : Mettre à jour le builder SDK pour base_url et options

**Files:**
- Modify: `sdk/src/agentforge/builder.py`
- Test: `sdk/tests/unit/test_builder.py` (tests de la méthode .model() à ajouter)

- [ ] **Step 1 : Modifier la méthode `.model()` dans builder.py**

Localiser la méthode `model` dans `sdk/src/agentforge/builder.py` (ligne ~81) :

```python
def model(self, provider: str, model: str, temperature: float = 0.7) -> "AgentBuilder":
    self._model_config = AgentModelConfig(
        provider=provider,
        model=model,
        temperature=temperature
    )
    return self
```

Remplacer par :

```python
def model(
    self,
    provider: str,
    model: str,
    temperature: float = 0.7,
    base_url: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> "AgentBuilder":
    self._model_config = AgentModelConfig(
        provider=provider,
        model=model,
        temperature=temperature,
        base_url=base_url,
        options=options or {},
    )
    return self
```

- [ ] **Step 2 : Créer sdk/tests/unit/test_builder.py**

```python
import json
import pytest
from agentforge.builder import Agent, AgentBuilder, AgentPolicy
from agentforge.types import AgentDefinition, PolicyConfig


class TestAgentBuilderModel:
    def test_default_model(self):
        agent = Agent("test").llm_node("n1").build()
        assert agent.llm_model_config.provider == "openai"
        assert agent.llm_model_config.model == "gpt-4o"

    def test_ollama_model(self):
        agent = (
            Agent("test")
            .model("ollama", "llama3.2", base_url="http://localhost:11434")
            .llm_node("n1")
            .build()
        )
        assert agent.llm_model_config.provider == "ollama"
        assert agent.llm_model_config.model == "llama3.2"
        assert agent.llm_model_config.base_url == "http://localhost:11434"

    def test_ollama_model_with_options(self):
        agent = (
            Agent("test")
            .model("ollama", "llama3.2", options={"num_ctx": 8192})
            .llm_node("n1")
            .build()
        )
        assert agent.llm_model_config.options["num_ctx"] == 8192

    def test_model_chainable(self):
        builder = Agent("test").model("ollama", "llama3.2")
        assert isinstance(builder, AgentBuilder)


class TestAgentBuilderNodes:
    def test_llm_node(self):
        agent = Agent("test").llm_node("chat", system_prompt="Be helpful").build()
        assert len(agent.graph_definition.nodes) == 1
        node = agent.graph_definition.nodes[0]
        assert node.id == "chat"
        assert node.type == "llm"
        assert node.config["system_prompt"] == "Be helpful"

    def test_tool_node(self):
        agent = Agent("test").tool_node("search", tool_name="web_search").build()
        node = agent.graph_definition.nodes[0]
        assert node.type == "tool"
        assert node.config["tool_name"] == "web_search"

    def test_subagent_node(self):
        agent = Agent("test").subagent_node("delegate", agent_id="uuid-123").build()
        node = agent.graph_definition.nodes[0]
        assert node.type == "subagent"
        assert node.config["agent_id"] == "uuid-123"

    def test_custom_node(self):
        agent = Agent("test").custom_node("step1", "my_type", {"key": "val"}).build()
        node = agent.graph_definition.nodes[0]
        assert node.type == "my_type"
        assert node.config["key"] == "val"

    def test_first_node_becomes_entry_point(self):
        agent = (
            Agent("test")
            .llm_node("first")
            .tool_node("second", tool_name="search")
            .build()
        )
        assert agent.graph_definition.entry_point == "first"

    def test_multiple_nodes(self):
        agent = (
            Agent("test")
            .llm_node("n1")
            .tool_node("n2", tool_name="t")
            .llm_node("n3")
            .build()
        )
        assert len(agent.graph_definition.nodes) == 3


class TestAgentBuilderEdges:
    def test_simple_edge(self):
        agent = (
            Agent("test")
            .llm_node("a")
            .llm_node("b")
            .edge("a", "b")
            .build()
        )
        assert len(agent.graph_definition.edges) == 1
        edge = agent.graph_definition.edges[0]
        assert edge.from_ == "a"
        assert edge.to == "b"

    def test_conditional_edge(self):
        agent = (
            Agent("test")
            .llm_node("a")
            .llm_node("b")
            .edge("a", "b", condition="yes", condition_type="contains")
            .build()
        )
        edge = agent.graph_definition.edges[0]
        assert edge.condition == "yes"
        assert edge.condition_type == "contains"

    def test_parallel_nodes(self):
        agent = (
            Agent("test")
            .llm_node("a")
            .llm_node("b")
            .parallel_nodes("a", "b")
            .build()
        )
        assert "a" in agent.graph_definition.parallel_nodes
        assert "b" in agent.graph_definition.parallel_nodes


class TestAgentBuilderSkills:
    def test_add_skill_instruction(self):
        agent = (
            Agent("test")
            .llm_node("n1")
            .skill("summarizer", skill_type="instruction", instructions="Summarize")
            .build()
        )
        assert len(agent.skills) == 1
        assert agent.skills[0].name == "summarizer"
        assert agent.skills[0].skill_type == "instruction"

    def test_add_skill_code(self):
        agent = (
            Agent("test")
            .llm_node("n1")
            .skill("calc", skill_type="code", source_code="def run(x): return x")
            .build()
        )
        assert agent.skills[0].skill_type == "code"


class TestAgentBuilderExportJson:
    def test_export_json_round_trip(self, tmp_path):
        filepath = str(tmp_path / "agent.json")
        (
            Agent("MyBot")
            .model("ollama", "llama3.2")
            .llm_node("chat", system_prompt="Hello")
            .build_and_export(filepath)
        )
        import json
        with open(filepath) as f:
            data = json.load(f)
        assert data["name"] == "MyBot"
        assert data["model_config"]["provider"] == "ollama"
        assert data["graph_definition"]["nodes"][0]["id"] == "chat"

    def test_build_returns_agent_definition(self):
        result = Agent("test").llm_node("n").build()
        assert isinstance(result, AgentDefinition)
```

**Note :** `build_and_export` n'existe pas encore. On va l'ajouter dans le step suivant avec le `export_json` renommé.

- [ ] **Step 3 : Lancer les tests → vérifier les failures**

```bash
cd sdk && pytest tests/unit/test_builder.py -v
```

Expected : la plupart PASSED sauf `test_export_json_round_trip` → `AttributeError: 'AgentBuilder' object has no attribute 'build_and_export'`.

- [ ] **Step 4 : Ajouter `build_and_export` comme alias de `export_json` dans builder.py**

Dans `AgentBuilder`, après la méthode `export_json` existante, ajouter :

```python
def build_and_export(self, filepath: str) -> None:
    """Alias de export_json pour la compatibilité avec les plans."""
    self.export_json(filepath)
```

- [ ] **Step 5 : Lancer les tests → tous passent**

```bash
cd sdk && pytest tests/unit/test_builder.py -v
```

Expected : tous PASSED.

- [ ] **Step 6 : Commit**

```bash
git add sdk/src/agentforge/builder.py sdk/tests/unit/test_builder.py
git commit -m "feat(sdk): builder.model() accepts base_url/options, add build_and_export alias"
```

---

## Task 6 : Tests AgentPolicy

**Files:**
- Create: `sdk/tests/unit/test_policy.py`

- [ ] **Step 1 : Créer sdk/tests/unit/test_policy.py**

```python
from agentforge.builder import AgentPolicy
from agentforge.types import PolicyConfig


class TestAgentPolicy:
    def test_empty_policy(self):
        policy = AgentPolicy().build()
        assert isinstance(policy, PolicyConfig)
        assert policy.denied_tools == []
        assert policy.allowed_tools is None

    def test_allow_tools(self):
        policy = AgentPolicy().allow_tools("web_search", "calc").build()
        assert "web_search" in policy.allowed_tools
        assert "calc" in policy.allowed_tools

    def test_deny_tool(self):
        policy = AgentPolicy().deny_tool("exec", "shell").build()
        assert "exec" in policy.denied_tools
        assert "shell" in policy.denied_tools

    def test_require_approval_for(self):
        policy = AgentPolicy().require_approval_for("send_email").build()
        assert "send_email" in policy.require_human_approval_for

    def test_deny_input_pattern(self):
        policy = AgentPolicy().deny_input_pattern("ignore previous").build()
        assert "ignore previous" in policy.deny_patterns

    def test_max_cost(self):
        policy = AgentPolicy().max_cost(0.50).build()
        assert policy.max_cost_usd == 0.50

    def test_max_steps(self):
        policy = AgentPolicy().max_steps(5).build()
        assert policy.max_graph_steps == 5

    def test_allow_fetch_only(self):
        policy = AgentPolicy().allow_fetch_only("https://api.example.com").build()
        assert "https://api.example.com" in policy.allowed_fetch_url_prefixes

    def test_max_message_history(self):
        policy = AgentPolicy().max_message_history(20).build()
        assert policy.max_message_history == 20

    def test_context_compression_threshold(self):
        policy = AgentPolicy().context_compression_threshold(4000).build()
        assert policy.context_compression_threshold == 4000

    def test_chaining(self):
        policy = (
            AgentPolicy()
            .max_cost(1.0)
            .max_steps(10)
            .deny_tool("exec")
            .allow_tools("search")
            .build()
        )
        assert policy.max_cost_usd == 1.0
        assert policy.max_graph_steps == 10
        assert "exec" in policy.denied_tools
        assert "search" in policy.allowed_tools

    def test_policy_passed_to_builder(self):
        from agentforge.builder import Agent
        policy = AgentPolicy().max_cost(0.1).max_steps(3)
        agent = Agent("test").llm_node("n1").policy(policy).build()
        assert agent.execution_policy is not None
        assert agent.execution_policy.max_cost_usd == 0.1
        assert agent.execution_policy.max_graph_steps == 3
```

- [ ] **Step 2 : Lancer les tests**

```bash
cd sdk && pytest tests/unit/test_policy.py -v
```

Expected : tous PASSED (AgentPolicy existe déjà, on vérifie juste le comportement).

- [ ] **Step 3 : Commit**

```bash
git add sdk/tests/unit/test_policy.py
git commit -m "test(sdk): add comprehensive AgentPolicy unit tests"
```

---

## Task 7 : Tests graph_validate

**Files:**
- Create: `sdk/tests/unit/test_graph_validate.py`

- [ ] **Step 1 : Créer sdk/tests/unit/test_graph_validate.py**

```python
import pytest
from pydantic import ValidationError
from agentforge.graph_validate import (
    GraphDefinitionValidated,
    GraphEdge,
    GraphNode,
    parse_and_validate_graph,
)


class TestParseAndValidateGraph:
    def test_valid_single_node(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": [],
            "entry_point": "n1",
        }
        gd = parse_and_validate_graph(raw)
        assert gd.entry_point == "n1"
        assert len(gd.nodes) == 1

    def test_auto_entry_point_from_first_node(self):
        raw = {
            "nodes": [{"id": "first", "type": "llm", "config": {}}],
        }
        gd = parse_and_validate_graph(raw)
        assert gd.entry_point == "first"

    def test_empty_nodes_raises(self):
        with pytest.raises(ValueError, match="nodes must be non-empty"):
            parse_and_validate_graph({"nodes": []})

    def test_none_input_raises(self):
        with pytest.raises(ValueError, match="nodes must be non-empty"):
            parse_and_validate_graph(None)

    def test_entry_point_not_in_nodes_raises(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "entry_point": "nonexistent",
        }
        with pytest.raises(ValueError, match="entry_point"):
            parse_and_validate_graph(raw)

    def test_edge_from_unknown_node_raises(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": [{"from": "unknown", "to": "n1"}],
            "entry_point": "n1",
        }
        with pytest.raises(ValueError, match="edge from unknown node"):
            parse_and_validate_graph(raw)

    def test_edge_to_unknown_node_raises(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": [{"from": "n1", "to": "unknown"}],
            "entry_point": "n1",
        }
        with pytest.raises(ValueError, match="edge to unknown node"):
            parse_and_validate_graph(raw)

    def test_edge_to_end_is_valid(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": [{"from": "n1", "to": "END"}],
            "entry_point": "n1",
        }
        gd = parse_and_validate_graph(raw)
        assert gd.edges[0].to == "END"

    def test_edge_from_start_is_valid(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": [{"from": "START", "to": "n1"}],
            "entry_point": "n1",
        }
        gd = parse_and_validate_graph(raw)
        assert gd.edges[0].from_ == "START"

    def test_parallel_nodes_valid(self):
        raw = {
            "nodes": [
                {"id": "a", "type": "llm", "config": {}},
                {"id": "b", "type": "llm", "config": {}},
            ],
            "entry_point": "a",
            "parallel_nodes": ["a", "b"],
        }
        gd = parse_and_validate_graph(raw)
        assert "a" in gd.parallel_nodes

    def test_parallel_node_unknown_raises(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "entry_point": "n1",
            "parallel_nodes": ["ghost"],
        }
        with pytest.raises(ValueError, match="parallel_nodes references unknown"):
            parse_and_validate_graph(raw)

    def test_to_dict_round_trip(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": [{"from": "n1", "to": "END"}],
            "entry_point": "n1",
        }
        gd = parse_and_validate_graph(raw)
        d = gd.to_dict()
        assert d["entry_point"] == "n1"
        assert d["edges"][0]["from"] == "n1"

    def test_schema_version_default(self):
        raw = {"nodes": [{"id": "n1", "config": {}}], "entry_point": "n1"}
        gd = parse_and_validate_graph(raw)
        assert gd.graph_schema_version == "1.0"

    def test_custom_schema_version(self):
        raw = {
            "nodes": [{"id": "n1", "config": {}}],
            "entry_point": "n1",
            "graph_schema_version": "2.0",
        }
        gd = parse_and_validate_graph(raw)
        assert gd.graph_schema_version == "2.0"
```

- [ ] **Step 2 : Lancer les tests**

```bash
cd sdk && pytest tests/unit/test_graph_validate.py -v
```

Expected : tous PASSED.

- [ ] **Step 3 : Commit**

```bash
git add sdk/tests/unit/test_graph_validate.py
git commit -m "test(sdk): add graph_validate unit tests"
```

---

## Task 8 : Tests AFG YAML

**Files:**
- Create: `sdk/tests/unit/test_afg_yaml.py`

- [ ] **Step 1 : Créer sdk/tests/unit/test_afg_yaml.py**

```python
import pytest
from pathlib import Path
from agentforge.afg_yaml import compile_afg_yaml_to_export, load_afg_yaml


VALID_YAML_CONTENT = """\
name: TestAgent
description: A test agent
model_config:
  provider: ollama
  model: llama3.2
  temperature: 0.7
graph_definition:
  nodes:
    - id: chat
      type: llm
      config:
        system_prompt: "Hello"
  edges:
    - from: chat
      to: END
  entry_point: chat
skills: []
execution_policy:
  max_graph_steps: 5
"""


class TestLoadAfgYaml:
    def test_load_valid_yaml(self, tmp_path):
        p = tmp_path / "agent.afg.yaml"
        p.write_text(VALID_YAML_CONTENT, encoding="utf-8")
        data = load_afg_yaml(p)
        assert data["name"] == "TestAgent"
        assert data["model_config"]["provider"] == "ollama"

    def test_load_invalid_yaml_raises(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("- just a list\n- not a mapping", encoding="utf-8")
        with pytest.raises(ValueError, match="root must be a mapping"):
            load_afg_yaml(p)


class TestCompileAfgYamlToExport:
    def test_valid_compile(self):
        data = {
            "name": "MyAgent",
            "description": "desc",
            "model_config": {"provider": "ollama", "model": "llama3.2", "temperature": 0.7},
            "graph_definition": {
                "nodes": [{"id": "n1", "type": "llm", "config": {}}],
                "entry_point": "n1",
            },
        }
        export = compile_afg_yaml_to_export(data)
        assert export["name"] == "MyAgent"
        assert "graph_definition" in export
        assert export["graph_definition"]["entry_point"] == "n1"

    def test_model_config_preserved(self):
        data = {
            "model_config": {"provider": "ollama", "model": "llama3.2", "temperature": 0.5},
            "graph_definition": {
                "nodes": [{"id": "n1", "config": {}}],
                "entry_point": "n1",
            },
        }
        export = compile_afg_yaml_to_export(data)
        assert export["model_config"]["provider"] == "ollama"

    def test_missing_graph_definition_raises(self):
        with pytest.raises(ValueError, match="graph_definition is required"):
            compile_afg_yaml_to_export({"name": "test"})

    def test_execution_policy_preserved(self):
        data = {
            "graph_definition": {
                "nodes": [{"id": "n1", "config": {}}],
                "entry_point": "n1",
            },
            "execution_policy": {"max_graph_steps": 10},
        }
        export = compile_afg_yaml_to_export(data)
        assert export["execution_policy"]["max_graph_steps"] == 10

    def test_optional_fields_omitted_when_none(self):
        data = {
            "graph_definition": {
                "nodes": [{"id": "n1", "config": {}}],
                "entry_point": "n1",
            },
        }
        export = compile_afg_yaml_to_export(data)
        assert "name" not in export
        assert "description" not in export

    def test_round_trip_from_file(self, tmp_path):
        p = tmp_path / "agent.afg.yaml"
        p.write_text(VALID_YAML_CONTENT, encoding="utf-8")
        raw = load_afg_yaml(p)
        export = compile_afg_yaml_to_export(raw)
        assert export["name"] == "TestAgent"
        assert export["model_config"]["provider"] == "ollama"
        assert export["graph_definition"]["nodes"][0]["id"] == "chat"
```

- [ ] **Step 2 : Lancer les tests**

```bash
cd sdk && pytest tests/unit/test_afg_yaml.py -v
```

Expected : tous PASSED.

- [ ] **Step 3 : Commit**

```bash
git add sdk/tests/unit/test_afg_yaml.py
git commit -m "test(sdk): add AFG YAML round-trip unit tests"
```

---

## Task 9 : Ollama dans le backend (llm_invoke.py)

**Files:**
- Modify: `backend/app/infrastructure/orchestration/llm_invoke.py`
- Modify: `backend/pyproject.toml`

- [ ] **Step 1 : Ajouter langchain-ollama dans backend/pyproject.toml**

Dans `backend/pyproject.toml`, dans le bloc `dependencies`, ajouter après `langchain-anthropic` :

```toml
"langchain-ollama>=0.3.0",
```

- [ ] **Step 2 : Ajouter le cas ollama dans invoke_chat_llm**

Dans `backend/app/infrastructure/orchestration/llm_invoke.py`, ajouter le nouveau bloc **avant** le `raise ValueError` final (après le bloc `if provider == "finetuned":`):

```python
    if provider == "ollama":
        model_name = str(model_config.get("model") or "llama3.2")
        base_url = str(model_config.get("base_url") or "http://localhost:11434")
        options: dict[str, Any] = model_config.get("options") or {}
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=base_url,
            **options,
        )
        out = await llm.ainvoke(lc_messages, config={"callbacks": callbacks})
        if isinstance(out, AIMessage):
            return str(out.content or ""), {}
        return str(getattr(out, "content", "") or out), {}
```

- [ ] **Step 3 : Mettre à jour la docstring de invoke_chat_llm**

Modifier la ligne de docstring :
```python
    `provider` in model_config: mock | openai | google | gemini | anthropic.
```
Par :
```python
    `provider` in model_config: mock | openai | google | gemini | anthropic | ollama.
```

- [ ] **Step 4 : Mettre à jour le raise ValueError final**

Remplacer :
```python
    raise ValueError(
        f"Unknown model_config.provider: {provider!r} "
        "(use mock, openai, google, gemini, anthropic, or finetuned)",
    )
```
Par :
```python
    raise ValueError(
        f"Unknown model_config.provider: {provider!r} "
        "(use mock, openai, google, gemini, anthropic, ollama, or finetuned)",
    )
```

- [ ] **Step 5 : Installer la dépendance backend**

```bash
cd backend && uv pip install -e ".[dev]"
```

- [ ] **Step 6 : Vérifier que les tests backend existants passent**

```bash
cd backend && pytest tests/ -v --ignore=tests/infrastructure -x -q
```

Expected : suite verte (les tests existants ne testent pas les providers LLM directement).

- [ ] **Step 7 : Commit**

```bash
git add backend/pyproject.toml backend/app/infrastructure/orchestration/llm_invoke.py
git commit -m "feat(backend): add ollama provider support in invoke_chat_llm"
```

---

## Task 10 : Lancer la suite complète SDK Python

- [ ] **Step 1 : Lancer tous les tests unitaires**

```bash
cd sdk && pytest tests/unit/ -v --tb=short
```

Expected :
```
tests/unit/test_afg_yaml.py ............  PASSED
tests/unit/test_builder.py ............  PASSED
tests/unit/test_graph_validate.py .....  PASSED
tests/unit/test_llm_factory.py .......   PASSED
tests/unit/test_policy.py .............  PASSED
tests/unit/test_types.py ..............  PASSED
```

- [ ] **Step 2 : Vérifier qu'aucun test d'intégration ne tourne**

```bash
cd sdk && pytest tests/ -m "not integration" -v
```

Expected : exactement les mêmes tests qu'au step 1, zéro test `integration`.

- [ ] **Step 3 : Commit de synthèse si nécessaire**

Si tout passe sans modification supplémentaire, créer un commit de tag :

```bash
git tag sdk-unit-tests-complete
```

---

## Task 11 : SDK TypeScript — Vitest setup

**Files:**
- Modify: `sdk-js/package.json`
- Create: `sdk-js/vitest.config.ts`

- [ ] **Step 1 : Mettre à jour package.json**

Remplacer le contenu de `sdk-js/package.json` par :

```json
{
  "name": "@agentforge/sdk",
  "version": "0.1.0",
  "description": "Minimal TypeScript SDK for AgentForge agent definitions.",
  "license": "MIT",
  "type": "module",
  "sideEffects": false,
  "files": [
    "dist",
    "README.md"
  ],
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "bin": {
    "agentforge": "./dist/cli.js"
  },
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js"
    }
  },
  "scripts": {
    "build": "tsc -p tsconfig.json",
    "clean": "rm -rf dist",
    "typecheck": "tsc -p tsconfig.json --noEmit",
    "gen:api": "openapi-typescript ../openapi/openapi.json -o src/generated/openapi.d.ts",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "publishConfig": {
    "access": "public"
  },
  "devDependencies": {
    "@types/node": "^25.5.0",
    "openapi-typescript": "^7.13.0",
    "typescript": "^5.8.2",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2 : Créer vitest.config.ts**

```typescript
// sdk-js/vitest.config.ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.spec.ts"],
  },
});
```

- [ ] **Step 3 : Installer vitest**

```bash
cd sdk-js && npm install
```

- [ ] **Step 4 : Vérifier que vitest tourne**

```bash
cd sdk-js && npm test
```

Expected : `No test files found` — pas d'erreur, juste aucun test pour l'instant.

- [ ] **Step 5 : Commit**

```bash
git add sdk-js/package.json sdk-js/vitest.config.ts
git commit -m "test(sdk-js): add vitest test runner"
```

---

## Task 12 : SDK TypeScript — Tests builder

**Files:**
- Create: `sdk-js/src/__tests__/builder.test.ts`

- [ ] **Step 1 : Créer sdk-js/src/__tests__/builder.test.ts**

```typescript
import { describe, it, expect } from "vitest";
import { Agent, AgentBuilder, AgentPolicy } from "../builder.js";
import type { AgentDefinition } from "../types.js";

describe("AgentBuilder", () => {
  describe("construction", () => {
    it("creates a builder with default name", () => {
      const builder = Agent();
      expect(builder).toBeInstanceOf(AgentBuilder);
    });

    it("creates a builder with custom name", () => {
      const builder = Agent("MyBot");
      expect(builder).toBeInstanceOf(AgentBuilder);
    });
  });

  describe(".model()", () => {
    it("sets openai model by default in build()", () => {
      const agent = Agent("test").llmNode("n1").build();
      expect(agent.model_config.provider).toBe("openai");
      expect(agent.model_config.model).toBe("gpt-4o");
    });

    it("sets ollama model", () => {
      const agent = Agent("test").model("ollama", "llama3.2").llmNode("n1").build();
      expect(agent.model_config.provider).toBe("ollama");
      expect(agent.model_config.model).toBe("llama3.2");
    });

    it("is chainable", () => {
      const builder = Agent("test").model("ollama", "llama3.2");
      expect(builder).toBeInstanceOf(AgentBuilder);
    });
  });

  describe(".llmNode()", () => {
    it("adds an llm node", () => {
      const agent = Agent("test").llmNode("chat", "Be helpful").build();
      expect(agent.graph_definition.nodes).toHaveLength(1);
      expect(agent.graph_definition.nodes[0].id).toBe("chat");
      expect(agent.graph_definition.nodes[0].type).toBe("llm");
      expect(agent.graph_definition.nodes[0].config.system_prompt).toBe("Be helpful");
    });

    it("first node becomes entry_point", () => {
      const agent = Agent("test").llmNode("first").llmNode("second").build();
      expect(agent.graph_definition.entry_point).toBe("first");
    });
  });

  describe(".toolNode()", () => {
    it("adds a tool node", () => {
      const agent = Agent("test").toolNode("search", "web_search").build();
      const node = agent.graph_definition.nodes[0];
      expect(node.type).toBe("tool");
      expect(node.config.tool_name).toBe("web_search");
    });
  });

  describe(".subagentNode()", () => {
    it("adds a subagent node", () => {
      const agent = Agent("test").subagentNode("delegate", "uuid-123").build();
      const node = agent.graph_definition.nodes[0];
      expect(node.type).toBe("subagent");
      expect(node.config.agent_id).toBe("uuid-123");
    });
  });

  describe(".customNode()", () => {
    it("adds a custom node type", () => {
      const agent = Agent("test").customNode("step1", "my_type", { key: "val" }).build();
      expect(agent.graph_definition.nodes[0].type).toBe("my_type");
    });
  });

  describe(".edge()", () => {
    it("adds a simple edge", () => {
      const agent = Agent("test").llmNode("a").llmNode("b").edge("a", "b").build();
      expect(agent.graph_definition.edges).toHaveLength(1);
      expect(agent.graph_definition.edges[0].from).toBe("a");
      expect(agent.graph_definition.edges[0].to).toBe("b");
    });

    it("adds a conditional edge", () => {
      const agent = Agent("test")
        .llmNode("a")
        .llmNode("b")
        .edge("a", "b", "yes", "contains")
        .build();
      expect(agent.graph_definition.edges[0].condition).toBe("yes");
      expect(agent.graph_definition.edges[0].condition_type).toBe("contains");
    });
  });

  describe(".parallelNodes()", () => {
    it("sets parallel node ids", () => {
      const agent = Agent("test")
        .llmNode("a")
        .llmNode("b")
        .parallelNodes("a", "b")
        .build();
      expect(agent.graph_definition.parallel_nodes).toContain("a");
      expect(agent.graph_definition.parallel_nodes).toContain("b");
    });
  });

  describe(".skill()", () => {
    it("adds an instruction skill", () => {
      const agent = Agent("test")
        .llmNode("n")
        .skill("summarizer", { skillType: "instruction", instructions: "Summarize" })
        .build();
      expect(agent.skills).toHaveLength(1);
      expect(agent.skills[0].name).toBe("summarizer");
      expect(agent.skills[0].skill_type).toBe("instruction");
    });
  });

  describe(".policy()", () => {
    it("attaches policy to agent definition", () => {
      const policy = new AgentPolicy().maxCost(0.5).maxSteps(5);
      const agent = Agent("test").llmNode("n").policy(policy).build();
      expect(agent.execution_policy?.max_cost_usd).toBe(0.5);
      expect(agent.execution_policy?.max_graph_steps).toBe(5);
    });
  });

  describe(".build()", () => {
    it("returns a complete AgentDefinition", () => {
      const agent: AgentDefinition = Agent("MyBot")
        .model("ollama", "llama3.2", 0.5)
        .llmNode("chat", "Be helpful")
        .build();
      expect(agent.name).toBe("MyBot");
      expect(agent.model_config.provider).toBe("ollama");
      expect(agent.graph_definition.nodes).toHaveLength(1);
    });

    it("build does not mutate builder state", () => {
      const builder = Agent("test").llmNode("n");
      const a1 = builder.build();
      const a2 = builder.build();
      expect(a1).not.toBe(a2);
      expect(a1.graph_definition.nodes).toHaveLength(1);
      expect(a2.graph_definition.nodes).toHaveLength(1);
    });
  });

  describe(".toJSON()", () => {
    it("produces valid JSON", () => {
      const json = Agent("test").llmNode("n").toJSON();
      const parsed = JSON.parse(json);
      expect(parsed.name).toBe("test");
    });

    it("produces pretty JSON with pretty=true", () => {
      const json = Agent("test").llmNode("n").toJSON(true);
      expect(json).toContain("\n");
    });
  });
});

describe("AgentPolicy", () => {
  it("builds empty policy", () => {
    const policy = new AgentPolicy().build();
    expect(policy).toEqual({});
  });

  it("sets allowed tools", () => {
    const policy = new AgentPolicy().allowTools("search", "calc").build();
    expect(policy.allowed_tools).toContain("search");
    expect(policy.allowed_tools).toContain("calc");
  });

  it("sets denied tools", () => {
    const policy = new AgentPolicy().denyTool("exec").build();
    expect(policy.denied_tools).toContain("exec");
  });

  it("sets max cost", () => {
    const policy = new AgentPolicy().maxCost(1.0).build();
    expect(policy.max_cost_usd).toBe(1.0);
  });

  it("sets max steps", () => {
    const policy = new AgentPolicy().maxSteps(10).build();
    expect(policy.max_graph_steps).toBe(10);
  });

  it("is chainable", () => {
    const policy = new AgentPolicy();
    expect(policy.maxCost(1).maxSteps(5)).toBe(policy);
  });
});
```

- [ ] **Step 2 : Lancer les tests**

```bash
cd sdk-js && npm test
```

Expected : tous PASSED.

- [ ] **Step 3 : Commit**

```bash
git add sdk-js/src/__tests__/builder.test.ts
git commit -m "test(sdk-js): add builder and AgentPolicy unit tests"
```

---

## Task 13 : SDK TypeScript — Tests types et client

**Files:**
- Create: `sdk-js/src/__tests__/types.test.ts`
- Create: `sdk-js/src/__tests__/client.test.ts`

- [ ] **Step 1 : Créer sdk-js/src/__tests__/types.test.ts**

```typescript
import { describe, it, expect } from "vitest";
import type {
  NodeConfig,
  EdgeConfig,
  GraphDefinition,
  AgentModelConfig,
  PolicyConfig,
  SkillSpec,
  AgentDefinition,
} from "../types.js";

describe("TypeScript types shape", () => {
  it("NodeConfig has required fields", () => {
    const node: NodeConfig = { id: "n1", type: "llm", config: {} };
    expect(node.id).toBe("n1");
    expect(node.type).toBe("llm");
  });

  it("NodeConfig accepts custom type", () => {
    const node: NodeConfig = { id: "n1", type: "my_custom", config: { key: 42 } };
    expect(node.type).toBe("my_custom");
  });

  it("EdgeConfig uses from/to", () => {
    const edge: EdgeConfig = { from: "a", to: "b", condition_type: "always" };
    expect(edge.from).toBe("a");
    expect(edge.to).toBe("b");
  });

  it("EdgeConfig condition is optional", () => {
    const edge: EdgeConfig = { from: "a", to: "b" };
    expect(edge.condition).toBeUndefined();
  });

  it("AgentModelConfig has required fields", () => {
    const mc: AgentModelConfig = { provider: "ollama", model: "llama3.2", temperature: 0.7 };
    expect(mc.provider).toBe("ollama");
  });

  it("PolicyConfig all fields optional", () => {
    const p: PolicyConfig = {};
    expect(p.max_cost_usd).toBeUndefined();
    expect(p.max_graph_steps).toBeUndefined();
  });

  it("PolicyConfig can set values", () => {
    const p: PolicyConfig = {
      max_cost_usd: 0.5,
      max_graph_steps: 10,
      denied_tools: ["exec"],
      allowed_tools: ["search"],
    };
    expect(p.max_cost_usd).toBe(0.5);
    expect(p.denied_tools).toContain("exec");
  });

  it("SkillSpec instruction type", () => {
    const s: SkillSpec = { name: "sum", skill_type: "instruction", instructions: "Summarize" };
    expect(s.skill_type).toBe("instruction");
  });

  it("SkillSpec code type", () => {
    const s: SkillSpec = { name: "calc", skill_type: "code", source_code: "def run(x): return x" };
    expect(s.skill_type).toBe("code");
  });

  it("AgentDefinition complete shape", () => {
    const agent: AgentDefinition = {
      name: "TestBot",
      graph_definition: {
        nodes: [{ id: "n1", type: "llm", config: {} }],
        edges: [],
        entry_point: "n1",
      },
      model_config: { provider: "ollama", model: "llama3.2", temperature: 0.7 },
      skills: [],
    };
    expect(agent.name).toBe("TestBot");
    expect(agent.description).toBeUndefined();
    expect(agent.execution_policy).toBeUndefined();
  });

  it("GraphDefinition with parallel_nodes", () => {
    const gd: GraphDefinition = {
      nodes: [
        { id: "a", type: "llm", config: {} },
        { id: "b", type: "llm", config: {} },
      ],
      edges: [],
      entry_point: "a",
      parallel_nodes: ["a", "b"],
    };
    expect(gd.parallel_nodes).toContain("a");
  });
});
```

- [ ] **Step 2 : Créer sdk-js/src/__tests__/client.test.ts**

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AgentClient } from "../client.js";

describe("AgentClient", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("constructor", () => {
    it("uses default apiUrl", () => {
      const client = new AgentClient();
      // On teste indirectement via push qui utilise this.apiUrl
      expect(client).toBeInstanceOf(AgentClient);
    });

    it("accepts custom config", () => {
      const client = new AgentClient({ apiUrl: "http://custom:9000", token: "mytoken" });
      expect(client).toBeInstanceOf(AgentClient);
    });
  });

  describe(".push()", () => {
    it("calls POST /api/v1/agents/import with agent JSON", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "agent-uuid-123" }),
      });
      vi.stubGlobal("fetch", mockFetch);

      const client = new AgentClient({ apiUrl: "http://localhost:8000", token: "tok" });
      const agentDef = {
        name: "TestBot",
        graph_definition: { nodes: [{ id: "n1", type: "llm", config: {} }], edges: [] },
        model_config: { provider: "ollama", model: "llama3.2", temperature: 0.7 },
        skills: [],
      };

      const result = await client.push(agentDef);

      expect(mockFetch).toHaveBeenCalledOnce();
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe("http://localhost:8000/api/v1/agents/import");
      expect(options.method).toBe("POST");
      expect(options.headers["Content-Type"]).toBe("application/json");
      expect(options.headers["Authorization"]).toBe("Bearer tok");
      expect(result.id).toBe("agent-uuid-123");
    });

    it("includes Bearer token in Authorization header", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "x" }),
      });
      vi.stubGlobal("fetch", mockFetch);

      const client = new AgentClient({ token: "secret-token" });
      await client.push({ name: "t", graph_definition: { nodes: [{ id: "n", type: "llm", config: {} }], edges: [] }, model_config: { provider: "openai", model: "gpt-4o", temperature: 0.7 }, skills: [] });

      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers["Authorization"]).toBe("Bearer secret-token");
    });

    it("throws on non-ok response", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        text: async () => "Unauthorized",
      }));

      const client = new AgentClient();
      await expect(
        client.push({ name: "t", graph_definition: { nodes: [{ id: "n", type: "llm", config: {} }], edges: [] }, model_config: { provider: "openai", model: "gpt-4o", temperature: 0.7 }, skills: [] })
      ).rejects.toThrow("Failed to push agent: 401");
    });

    it("accepts a JSON string payload", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "str-id" }),
      });
      vi.stubGlobal("fetch", mockFetch);

      const client = new AgentClient();
      const result = await client.push('{"name":"raw"}');
      expect(result.id).toBe("str-id");

      const [, options] = mockFetch.mock.calls[0];
      expect(options.body).toBe('{"name":"raw"}');
    });
  });

  describe(".pull()", () => {
    it("calls GET /api/v1/agents/{id}/export", async () => {
      const mockDef = {
        name: "PulledBot",
        graph_definition: { nodes: [], edges: [] },
        model_config: { provider: "openai", model: "gpt-4o", temperature: 0.7 },
        skills: [],
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockDef,
      }));

      const client = new AgentClient({ apiUrl: "http://localhost:8000" });
      const result = await client.pull("agent-uuid");
      expect(result.name).toBe("PulledBot");

      const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toContain("/api/v1/agents/agent-uuid/export");
    });

    it("throws on non-ok response", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        text: async () => "Not found",
      }));

      const client = new AgentClient();
      await expect(client.pull("bad-id")).rejects.toThrow("Failed to pull agent: 404");
    });
  });
});
```

- [ ] **Step 3 : Lancer les tests**

```bash
cd sdk-js && npm test
```

Expected : tous PASSED.

- [ ] **Step 4 : Commit**

```bash
git add sdk-js/src/__tests__/types.test.ts sdk-js/src/__tests__/client.test.ts
git commit -m "test(sdk-js): add types shape and AgentClient unit tests"
```

---

## Task 14 : Validation finale

- [ ] **Step 1 : Suite complète SDK Python**

```bash
cd sdk && pytest tests/unit/ -v --tb=short
```

Expected : toutes les suites vertes, 0 erreur.

- [ ] **Step 2 : Suite complète SDK TypeScript**

```bash
cd sdk-js && npm test
```

Expected : toutes les suites vertes, 0 erreur.

- [ ] **Step 3 : Tests backend**

```bash
cd backend && pytest tests/ -q --ignore=tests/infrastructure -x
```

Expected : suite verte (aucune régression introduite par l'ajout d'Ollama).

- [ ] **Step 4 : Vérifier typecheck SDK-JS**

```bash
cd sdk-js && npm run typecheck
```

Expected : 0 erreur TypeScript.

- [ ] **Step 5 : Commit de clôture Phase N1**

```bash
git add -A
git commit -m "feat: Phase N1 complete — Ollama provider + SDK unit tests (Python + TypeScript)"
```

---

## Self-Review

**Spec coverage :**
- ✅ Ollama provider SDK Python (`llm_factory.py`, Task 3)
- ✅ Ollama provider backend (`llm_invoke.py`, Task 9)
- ✅ `AgentModelConfig` + `base_url` + `options` (Task 2)
- ✅ Builder `.model()` étendu (Task 5)
- ✅ Tests unitaires SDK : builder, types, policy, graph_validate, afg_yaml, llm_factory (Tasks 2–8)
- ✅ Tests Vitest SDK-JS : builder, AgentPolicy, types, client (Tasks 12–13)

**Noms cohérents :**
- `build_llm()` nommé de façon identique dans `llm_factory.py` SDK et référencé dans `agent.py`
- `AgentModelConfig.base_url` et `AgentModelConfig.options` identiques dans `types.py` et utilisés dans `builder.py`
- `build_and_export()` est un alias de `export_json()` — référencé dans `test_builder.py` Task 5
