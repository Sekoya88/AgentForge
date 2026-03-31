"""Optional Modal speech smoke — run only with MODAL_SPEECH_SMOKE=1 in the environment."""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("MODAL_SPEECH_SMOKE") != "1",
        reason=("Set MODAL_SPEECH_SMOKE=1 (modal CLI + agentforge-finetune deployed)."),
    ),
]


def test_modal_speech_function_is_registered() -> None:
    import modal

    fn = modal.Function.from_name("agentforge-finetune", "train_speech_model")
    assert fn is not None
