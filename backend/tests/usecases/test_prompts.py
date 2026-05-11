"""プロンプトビルダーのユニットテスト。

BE-006 Acceptance:
  (a) build_draft_prompt が同じ入力で常に同じ出力を返す (決定論的)
  (b) 出力がシステムプロンプトヘッダーを含む
  (c) clinical_input がプロンプト本文にそのまま含まれる
  (d) 関数がロガーを一切呼び出さない
"""

from __future__ import annotations

import logging

import pytest

from app.usecases.prompts import DRAFT_SYSTEM_PROMPT, build_draft_prompt

# ---------------------------------------------------------------------------
# (a) 決定論的: 同じ入力で常に同じ出力
# ---------------------------------------------------------------------------


def test_build_draft_prompt_is_deterministic() -> None:
    """同じ clinical_input に対して常に同じプロンプトを返す。"""
    input_text = "患者は発熱、咳、倦怠感を訴えている。"
    result1 = build_draft_prompt(input_text)
    result2 = build_draft_prompt(input_text)
    assert result1 == result2


def test_build_draft_prompt_different_inputs_differ() -> None:
    """異なる clinical_input は異なるプロンプトを生成する。"""
    result1 = build_draft_prompt("頭痛と嘔吐")
    result2 = build_draft_prompt("胸痛と息切れ")
    assert result1 != result2


# ---------------------------------------------------------------------------
# (b) システムプロンプトヘッダーを含む
# ---------------------------------------------------------------------------


def test_build_draft_prompt_contains_system_prompt() -> None:
    """出力が DRAFT_SYSTEM_PROMPT を含む。"""
    result = build_draft_prompt("テスト入力")
    assert DRAFT_SYSTEM_PROMPT in result


def test_build_draft_prompt_contains_soap_markers() -> None:
    """出力が SOAP 形式の各セクションマーカーを含む。"""
    result = build_draft_prompt("テスト入力")
    # DRAFT_SYSTEM_PROMPT 内の SOAP セクション見出しを確認する
    assert "Subjective" in result
    assert "Objective" in result
    assert "Assessment" in result
    assert "Plan" in result


# ---------------------------------------------------------------------------
# (c) clinical_input がプロンプト本文にそのまま含まれる
# ---------------------------------------------------------------------------


def test_build_draft_prompt_contains_clinical_input_verbatim() -> None:
    """clinical_input がプロンプト本文にそのまま埋め込まれる。

    PHI はローカルモデルへのプロンプト本文に含まれることが許可されている
    (local-llm-and-phi.md §3)。
    """
    clinical_input = "患者: 山田太郎, MRN: 12345, 主訴: 38.5℃の発熱3日間"
    result = build_draft_prompt(clinical_input)
    assert clinical_input in result


# ---------------------------------------------------------------------------
# (d) 関数がロガーを呼び出さない
# ---------------------------------------------------------------------------


def test_build_draft_prompt_does_not_log(caplog: pytest.LogCaptureFixture) -> None:
    """build_draft_prompt はログ出力を一切行わない。"""
    with caplog.at_level(logging.DEBUG):
        build_draft_prompt("テスト臨床情報")
    # ログレコードがゼロであることを確認する
    assert len(caplog.records) == 0


def test_build_draft_prompt_module_has_no_logger() -> None:
    """prompts モジュールがロガーを持たないことを確認する。

    logging をインポートしないことがコードレベルで保証されている。
    """
    import app.usecases.prompts as prompts_module

    # prompts.py は logging をインポートしない — モジュール属性として logging が存在しない
    assert not hasattr(prompts_module, "logging")
