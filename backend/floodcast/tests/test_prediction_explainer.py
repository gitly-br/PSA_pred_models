from __future__ import annotations

import asyncio

from floodcast.prediction_explainer import (
    build_explanation_prompt,
    generate_short_explanation,
    normalize_short_explanation,
    _derive_operational_factors,
)


def _prediction(**overrides):
    base = {
        "bacia": "guarara",
        "day": "2026-05-02",
        "predict": 2,
        "severity": 3,
        "proba": 0.42,
        "feature_snapshot": {
            "api_070": 0.62,
            "api_085": 0.55,
            "api_095": 0.41,
            "acum_7d": 1.9,
            "acum_30d": 6.3,
            "pico_1h_lag1": 0.0,
            "horas_intensas_lag1": 0.0,
            "n_chovendo_max_lag1": 0.0,
        },
        "forecast_summary": {
            "total_mm": 12.5,
            "max_point_total_mm": 8.1,
            "rain_by_period_mm": {
                "night": 1.0,
                "morning": 2.0,
                "afternoon": 7.0,
                "evening": 2.5,
            },
        },
        "shap_explanation": [
            ("api_070", 0.31),
            ("acum_7d", 0.21),
            ("max_day_lag1", -0.08),
        ],
    }
    base.update(overrides)
    return base


def test_build_explanation_prompt_is_compact_and_contains_key_context():
    prompt = build_explanation_prompt(_prediction())

    assert "guarara" not in prompt
    assert "2026-05-02" not in prompt
    assert "predict=2" not in prompt
    assert "severity=3" not in prompt
    assert "proba=0.42" not in prompt
    assert "12.5" not in prompt
    assert "8.1" not in prompt
    assert "api_070" in prompt
    assert "acum_7d" in prompt
    assert "sinais_observados" in prompt
    assert "sinais_previstos" in prompt
    assert "fatores_SHAP_descricao" in prompt
    assert "chuva acumulada nos ultimos dias" in prompt
    assert "chuva concentrada em um periodo curto" in prompt
    assert "bacia carregada" not in prompt
    assert "solo saturado" in prompt
    assert "escoamento" in prompt
    assert "escala" in prompt
    assert len(prompt) < 1600


def test_build_explanation_prompt_handles_missing_shap():
    prompt = build_explanation_prompt(_prediction(shap_explanation=None))

    assert "sem SHAP" in prompt
    assert "total_mm" not in prompt
    assert "proba=0.42" not in prompt


def test_derive_operational_factors_translates_shap_names_into_leiga_language():
    factors = _derive_operational_factors(_prediction())

    assert "chuva acumulada nos ultimos dias" in factors["observado"]
    assert "chuva acumulada recente" in factors["observado"]
    assert "pancada de chuva acima do normal" not in factors["observado"]
    assert "chuva persistente" not in factors["observado"]
    assert "chuva concentrada em um periodo curto" in factors["previsto"]


def test_derive_operational_factors_separates_observed_from_forecast():
    factors = _derive_operational_factors(_prediction())

    assert len(factors["observado"]) > 0
    assert len(factors["previsto"]) > 0
    all_observed_labels = " ".join(factors["observado"])
    all_forecast_labels = " ".join(factors["previsto"])
    assert "acumulada" in all_observed_labels
    assert "concentrada" in all_forecast_labels


def test_normalize_short_explanation_single_line_and_limited():
    text = "  Risco moderado:\n chuva prevista à tarde e API recente elevada.  "

    result = normalize_short_explanation(text, max_chars=48)

    assert "\n" not in result
    assert result.startswith("Risco moderado:")
    assert len(result) <= 48


def test_generate_short_explanation_without_api_key_does_not_call_http(monkeypatch):
    calls = {"count": 0}

    async def fake_post(*args, **kwargs):
        calls["count"] += 1
        return {}

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = asyncio.run(generate_short_explanation(_prediction(), http_post=fake_post))

    assert result is None
    assert calls["count"] == 0


def test_generate_short_explanation_with_blank_api_key_does_not_call_http(monkeypatch):
    calls = {"count": 0}

    async def fake_post(*args, **kwargs):
        calls["count"] += 1
        return {}

    monkeypatch.setenv("OPENROUTER_API_KEY", "   ")

    result = asyncio.run(generate_short_explanation(_prediction(), http_post=fake_post))

    assert result is None
    assert calls["count"] == 0


def test_generate_short_explanation_success_uses_openrouter_contract(monkeypatch):
    captured = {}

    async def fake_post(url, headers, payload, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {
            "choices": [
                {"message": {"content": "Risco moderado: chuva à tarde e API recente elevada."}}
            ]
        }

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_EXPLANATION_MODEL", "cheap/model")
    monkeypatch.setenv("OPENROUTER_EXPLANATION_TIMEOUT_SECONDS", "1.5")

    result = asyncio.run(generate_short_explanation(_prediction(), http_post=fake_post))

    assert result == "Risco moderado: chuva à tarde e API recente elevada."
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "cheap/model"
    assert captured["timeout"] == 1.5
    assert captured["payload"]["messages"][-1]["content"] == build_explanation_prompt(_prediction())
    assert "2026-05-02" not in captured["payload"]["messages"][-1]["content"]
    assert "12.5" not in captured["payload"]["messages"][-1]["content"]


def test_generate_short_explanation_http_error_returns_none(monkeypatch):
    async def fake_post(*args, **kwargs):
        raise TimeoutError("too slow")

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    result = asyncio.run(generate_short_explanation(_prediction(), http_post=fake_post))

    assert result is None


def test_generate_short_explanation_invalid_response_returns_none(monkeypatch):
    async def fake_post(*args, **kwargs):
        return {"unexpected": "shape"}

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    result = asyncio.run(generate_short_explanation(_prediction(), http_post=fake_post))

    assert result is None
