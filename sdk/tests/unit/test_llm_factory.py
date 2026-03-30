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
        result = build_llm(provider="google", model="gemini-2.0-flash", temperature=0.3)
        MockGoogle.assert_called_once_with(model="gemini-2.0-flash", temperature=0.3)
        assert result is mock_instance

    @patch("agentforge.llm_factory.ChatGoogleGenerativeAI")
    def test_gemini_alias(self, MockGoogle):
        mock_instance = MagicMock()
        MockGoogle.return_value = mock_instance
        result = build_llm(provider="gemini", model="gemini-2.0-flash", temperature=0.3)
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
