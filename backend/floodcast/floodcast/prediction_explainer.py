from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.request


OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


def _derive_operational_factors(prediction: dict) -> dict[str, list[str]]:
    forecast = prediction.get("forecast_summary") or {}
    snapshot = prediction.get("feature_snapshot") or {}
    shap_values = prediction.get("shap_explanation") or []
    feature_names = [name for name, _value in shap_values]
    observed: list[str] = []
    forecasted: list[str] = []

    api_strength = max(
        [float(snapshot.get(name) or 0.0) for name in ("api_070", "api_085", "api_095") if name in snapshot],
        default=0.0,
    )
    if api_strength > 0:
        observed.append("chuva acumulada nos ultimos dias")

    if float(snapshot.get("acum_7d") or 0.0) > 0 or float(snapshot.get("acum_30d") or 0.0) > 0:
        observed.append("chuva acumulada recente")

    if float(snapshot.get("pico_1h_lag1") or 0.0) > 0 or float(snapshot.get("horas_intensas_lag1") or 0.0) > 0:
        observed.append("pancada de chuva acima do normal")

    if float(snapshot.get("n_chovendo_max_lag1") or 0.0) > 0:
        observed.append("chuva persistente")

    if not observed and any(name.startswith("api_") for name in feature_names):
        observed.append("chuva acumulada nos ultimos dias")

    rain_by_period = forecast.get("rain_by_period_mm") or {}
    if rain_by_period:
        positive_periods = [float(value or 0.0) for value in rain_by_period.values() if float(value or 0.0) > 0]
        if positive_periods:
            dominant = max(positive_periods)
            total = sum(positive_periods)
            if total > 0 and dominant / total >= 0.55:
                forecasted.append("chuva concentrada em um periodo curto")
            elif len(positive_periods) >= 3:
                forecasted.append("chuva distribuida ao longo do dia")

    if not observed and not forecasted:
        observed.append("chuva sem sinal claro de acumulado ou pancada forte")

    def _dedup(items: list[str]) -> list[str]:
        seen: list[str] = []
        for item in items:
            if item not in seen:
                seen.append(item)
        return seen

    return {"observado": _dedup(observed), "previsto": _dedup(forecasted)}


def _humanize_feature_name(name: str) -> str:
    if name.startswith("api_"):
        return "chuva acumulada recente"
    if name in {"acum_7d", "acum_30d"}:
        return "chuva acumulada nos ultimos dias"
    if name == "pico_1h_lag1":
        return "pancada forte recente"
    if name == "horas_intensas_lag1":
        return "horas de chuva intensa recentes"
    if name == "n_chovendo_max_lag1":
        return "chuva persistente recente"
    if name.startswith("max_day_lag"):
        return "pico diario de chuva ontem"
    return name.replace("_", " ")


def build_explanation_prompt(prediction: dict) -> str:
    shap_values = prediction.get("shap_explanation") or []
    factors = _derive_operational_factors(prediction)
    if shap_values:
        top_shap = shap_values[:3]
        shap_text = ", ".join(name for name, _value in top_shap)
        shap_hints = ", ".join(
            f"{name}={_humanize_feature_name(name)}" for name, _value in top_shap
        )
    else:
        shap_text = "sem SHAP"
        shap_hints = "sem SHAP"

    observado = ", ".join(factors["observado"]) if factors["observado"] else "nenhum"
    previsto = ", ".join(factors["previsto"]) if factors["previsto"] else "nenhum"

    return (
        "Explique em uma frase curta, em portugues do Brasil, por que o alerta foi ou nao acionado. "
        "Use linguagem leiga, direta e concreta. Nao mencione escala, limiar, valor, porcentagem, severidade, milimetros, numeros ou detalhes internos. "
        "Descreva apenas os 2 ou 3 features mais importantes que o SHAP apontou. "
        "Nao use frases genericas, conclusoes abstratas ou consequencias. "
        "Nao mencione deslizamento, solo saturado, escoamento ou absorcao. "
        "Saida desejada: 'Houve muita chuva nos ultimos dias e vai continuar chovendo no periodo da tarde.'. "
        "Sinais observados ja aconteceram: use verbo no passado e cite a chuva recente. "
        "Sinais previstos vao acontecer: use verbo no futuro e cite o periodo do dia quando houver concentracao. "
        "Nunca misture passado e futuro na mesma frase. "
        f"sinais_observados={observado}; "
        f"sinais_previstos={previsto}; "
        f"fatores_SHAP={shap_text}; "
        f"fatores_SHAP_descricao={shap_hints}; "
        "responda apenas com a justificativa final, sem bullet points e sem numeros."
    )


def normalize_short_explanation(text: str | None, max_chars: int = 180) -> str | None:
    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return None
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rstrip()


async def _default_http_post(url: str, headers: dict, payload: dict, timeout: float) -> dict:
    def post() -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    return await asyncio.to_thread(post)


async def generate_short_explanation(prediction: dict, http_post=None) -> str | None:
    api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return None

    post = http_post or _default_http_post
    model = os.getenv("OPENROUTER_EXPLANATION_MODEL", "openai/gpt-4o-mini")
    try:
        timeout = float(os.getenv("OPENROUTER_EXPLANATION_TIMEOUT_SECONDS", "8.0"))
    except ValueError:
        timeout = 8.0

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Responda com uma unica frase curta, clara e acionavel. "
                    "Nao use numeros, datas, porcentagens, severidade ou medidas. "
                    "Frase generica proibida: 'a chuva que caiu pode causar'. "
                    "Explique apenas o motivo humano do alerta, em linguagem leiga. "
                    "Nao mencione deslizamento, solo saturado, escoamento ou absorcao. "
                    "Sinais observados = passado; sinais previstos = futuro. Nunca misture. "
                    "Mencione periodo do dia quando sinais previstos existirem."
                ),
            },
            {"role": "user", "content": build_explanation_prompt(prediction)},
        ],
        "temperature": 0.1,
        "max_tokens": 120,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = await post(OPENROUTER_CHAT_COMPLETIONS_URL, headers, payload, timeout)
        content = response["choices"][0]["message"]["content"]
    except Exception:
        return None
    return normalize_short_explanation(content)
