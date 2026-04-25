"""Local speech providers (OpenAI Whisper / TTS) for SDK execution."""

from agentforge.speech.openai_tts import LocalOpenAITTS
from agentforge.speech.openai_whisper import LocalWhisperASR

__all__ = ["LocalWhisperASR", "LocalOpenAITTS"]
