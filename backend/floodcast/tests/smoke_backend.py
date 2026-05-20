"""
Smoke test idempotente para 3 cenarios reais do backend local PSA.

Cenarios:
1. Cache hit: data com inference ja cacheada no MongoDB.
2. On-demand: data sem inference no Mongo, mas com historico+forecast suficientes.
3. Fallback parquet: data sem dados no Mongo, mas com dados apenas via fallback MinIO.

Uso:
    cd /home/rnicola/Documents/Projects/PSA
    python backend/floodcast/tests/smoke_backend.py

Requisitos:
    - docker-compose.project.yml rodando (mongo, minio, sentry)
    - dependencias do floodcast instaladas
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

import httpx
import pytz

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND / "floodcast"))
sys.path.insert(0, str(BACKEND / "harvest"))
sys.path.insert(0, str(BACKEND / "sentry" / "source"))

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://psa:psa@localhost:16521/?authSource=admin")
SENTRY_URL = os.getenv("SENTRY_URL", "http://localhost:8080")

# Datas deterministicas para cada cenario
DATE_CACHED = date(2025, 4, 21)      # Cenario 1: ja existe inference
DATE_ON_DEMAND = date(2025, 4, 1)    # Cenario 2: tem dados no Mongo, sem inference
DATE_FALLBACK = date(2025, 2, 15)    # Cenario 3: sem dados no Mongo, tem no MinIO


class SmokeFailure(RuntimeError):
    pass


SP_TZ = pytz.timezone("America/Sao_Paulo")


def _mongo_client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(MONGO_URI)


async def cleanup_inference(target_date: date):
    """Remove inference para uma data especifica (idempotencia)."""
    client = _mongo_client()
    db = client.floodcast
    dt_start = SP_TZ.localize(datetime.combine(target_date, time.min))
    dt_end = SP_TZ.localize(datetime.combine(target_date, time.max))
    result = await db.inference.delete_many({
        "dt_key": {"$gte": dt_start, "$lte": dt_end},
        "region": "all"
    })
    client.close()
    return result.deleted_count


async def cleanup_api_data(target_date: date):
    """Remove dados de api_data para uma data especifica (fallback cenario)."""
    client = _mongo_client()
    db = client.api_data
    dt_start = SP_TZ.localize(datetime.combine(target_date, time.min))
    dt_end = SP_TZ.localize(datetime.combine(target_date, time.max))
    # Remove forecast para a data
    forecast_deleted = await db.forecast.delete_many({
        "dt_request": {"$gte": dt_start, "$lte": dt_end}
    })
    # Remove historic para 90 dias antes ate a data
    hist_start = SP_TZ.localize(datetime.combine(target_date, time.min)) - timedelta(days=90)
    historic_deleted = await db.historic.delete_many({
        "dt": {"$gte": hist_start, "$lte": dt_end}
    })
    client.close()
    return forecast_deleted.deleted_count, historic_deleted.deleted_count


async def check_inference_exists(target_date: date) -> bool:
    """Verifica se existe inference para a data."""
    client = _mongo_client()
    db = client.floodcast
    dt_start = SP_TZ.localize(datetime.combine(target_date, time.min))
    count = await db.inference.count_documents({
        "dt_key": {"$gte": dt_start},
        "region": "all"
    })
    client.close()
    return count > 0


async def check_api_data_exists(target_date: date) -> tuple[bool, bool]:
    """Verifica se existe forecast e historic para a data no MongoDB."""
    client = _mongo_client()
    db = client.api_data
    dt_start = SP_TZ.localize(datetime.combine(target_date, time.min))
    dt_end = SP_TZ.localize(datetime.combine(target_date, time.max))

    forecast_count = await db.forecast.count_documents({
        "dt_request": {"$gte": dt_start, "$lte": dt_end}
    })

    hist_start = SP_TZ.localize(datetime.combine(target_date, time.min)) - timedelta(days=90)
    historic_count = await db.historic.count_documents({
        "dt": {"$gte": hist_start, "$lte": dt_end}
    })

    client.close()
    return forecast_count > 0, historic_count > 0


def _validate_inference_payload(payload: dict, scenario_name: str):
    """Valida estrutura minima da resposta de inferencia."""
    required_top = {"predict", "severity", "proba", "explanation", "rain_today", "forecast_summary", "models"}
    missing = required_top - set(payload.keys())
    if missing:
        raise SmokeFailure(f"[{scenario_name}] Campos obrigatorios faltando: {missing}")
    
    if not isinstance(payload["predict"], int):
        raise SmokeFailure(f"[{scenario_name}] predict deve ser int, got {type(payload['predict'])}")
    if not isinstance(payload["severity"], int):
        raise SmokeFailure(f"[{scenario_name}] severity deve ser int, got {type(payload['severity'])}")
    if payload["proba"] is not None and not isinstance(payload["proba"], (int, float)):
        raise SmokeFailure(f"[{scenario_name}] proba deve ser numero, got {type(payload['proba'])}")
    if not isinstance(payload["explanation"], str):
        raise SmokeFailure(f"[{scenario_name}] explanation deve ser str, got {type(payload['explanation'])}")
    if not isinstance(payload["rain_today"], dict):
        raise SmokeFailure(f"[{scenario_name}] rain_today deve ser dict, got {type(payload['rain_today'])}")
    if not isinstance(payload["forecast_summary"], dict):
        raise SmokeFailure(f"[{scenario_name}] forecast_summary deve ser dict, got {type(payload['forecast_summary'])}")
    if not isinstance(payload["models"], dict):
        raise SmokeFailure(f"[{scenario_name}] models deve ser dict, got {type(payload['models'])}")


async def call_api(region: str, target_date: date) -> dict:
    """Chama a API do Sentry e retorna o payload JSON."""
    url = f"{SENTRY_URL}/region/{region}"
    params = {"date": target_date.isoformat()}
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, params=params)
    return response


async def run_scenario_1_cache_hit():
    """Cenario 1: inference ja cacheada no MongoDB."""
    scenario = "CENARIO_1_CACHE_HIT"
    target_date = DATE_CACHED
    
    print(f"\n=== {scenario}: {target_date} ===")
    
    # Pre-condicao: inference deve existir
    exists = await check_inference_exists(target_date)
    if not exists:
        raise SmokeFailure(f"[{scenario}] Pre-condicao falhou: inference nao existe para {target_date}")
    print(f"[{scenario}] Pre-condicao OK: inference existe")
    
    # Acao: chamar API
    response = await call_api("all", target_date)
    
    # Validacao
    if response.status_code != 200:
        raise SmokeFailure(f"[{scenario}] HTTP {response.status_code}: {response.text}")
    
    payload = response.json()
    _validate_inference_payload(payload, scenario)
    
    # Validacao adicional: deve ter vindo do cache (tempo rapido ou verificar se nao gerou novo)
    # Como nao temos como saber se veio do cache diretamente, validamos que o resultado eh consistente
    print(f"[{scenario}] predict={payload['predict']}, severity={payload['severity']}, proba={payload['proba']}")
    print(f"[{scenario}] SUCESSO")
    return payload


async def run_scenario_2_on_demand():
    """Cenario 2: sem inference no Mongo, mas com historico+forecast suficientes."""
    scenario = "CENARIO_2_ON_DEMAND"
    target_date = DATE_ON_DEMAND
    
    print(f"\n=== {scenario}: {target_date} ===")
    
    # Pre-condicao: limpar inference se existir (idempotencia)
    deleted = await cleanup_inference(target_date)
    if deleted > 0:
        print(f"[{scenario}] Limpou {deleted} inference(s) existente(s)")
    
    # Pre-condicao: dados devem existir no MongoDB
    has_forecast, has_historic = await check_api_data_exists(target_date)
    if not has_forecast:
        raise SmokeFailure(f"[{scenario}] Pre-condicao falhou: sem forecast no MongoDB para {target_date}")
    if not has_historic:
        raise SmokeFailure(f"[{scenario}] Pre-condicao falhou: sem historico no MongoDB para {target_date}")
    print(f"[{scenario}] Pre-condicao OK: forecast={has_forecast}, historico={has_historic}")
    
    # Acao: chamar API (deve gerar on-demand)
    response = await call_api("all", target_date)
    
    # Validacao
    if response.status_code != 200:
        raise SmokeFailure(f"[{scenario}] HTTP {response.status_code}: {response.text}")
    
    payload = response.json()
    _validate_inference_payload(payload, scenario)
    
    # Pos-condicao: inference deve ter sido criada
    exists_after = await check_inference_exists(target_date)
    if not exists_after:
        raise SmokeFailure(f"[{scenario}] Pos-condicao falhou: inference nao foi persistida apos on-demand")
    
    print(f"[{scenario}] predict={payload['predict']}, severity={payload['severity']}, proba={payload['proba']}")
    print(f"[{scenario}] SUCESSO")
    return payload


async def run_scenario_3_fallback():
    """Cenario 3: sem dados no Mongo, mas com fallback parquet no MinIO."""
    scenario = "CENARIO_3_FALLBACK"
    target_date = DATE_FALLBACK
    
    print(f"\n=== {scenario}: {target_date} ===")
    
    # Pre-condicao: limpar inference se existir (idempotencia)
    deleted_inf = await cleanup_inference(target_date)
    if deleted_inf > 0:
        print(f"[{scenario}] Limpou {deleted_inf} inference(s) existente(s)")
    
    # Pre-condicao: dados NAO devem existir no MongoDB (data naturalmente sem dados)
    has_forecast, has_historic = await check_api_data_exists(target_date)
    if has_forecast or has_historic:
        raise SmokeFailure(f"[{scenario}] Pre-condicao falhou: ainda existem dados no MongoDB (forecast={has_forecast}, historico={has_historic})")
    print(f"[{scenario}] Pre-condicao OK: sem dados no MongoDB")
    
    # Acao: chamar API (deve usar fallback MinIO)
    response = await call_api("all", target_date)
    
    # Validacao
    if response.status_code != 200:
        raise SmokeFailure(f"[{scenario}] HTTP {response.status_code}: {response.text}")
    
    payload = response.json()
    _validate_inference_payload(payload, scenario)
    
    # Pos-condicao: inference deve ter sido criada
    exists_after = await check_inference_exists(target_date)
    if not exists_after:
        raise SmokeFailure(f"[{scenario}] Pos-condicao falhou: inference nao foi persistida apos fallback")
    
    print(f"[{scenario}] predict={payload['predict']}, severity={payload['severity']}, proba={payload['proba']}")
    print(f"[{scenario}] SUCESSO")
    return payload


async def run_smoke():
    print("=" * 60)
    print("SMOKE TEST BACKEND PSA")
    print("=" * 60)
    print(f"MongoDB: {MONGO_URI}")
    print(f"Sentry API: {SENTRY_URL}")
    print(f"Datas: cache={DATE_CACHED}, on-demand={DATE_ON_DEMAND}, fallback={DATE_FALLBACK}")
    
    results = {}
    
    try:
        results["cenario_1"] = await run_scenario_1_cache_hit()
    except SmokeFailure as e:
        results["cenario_1"] = f"FALHA: {e}"
        print(str(e))
    
    try:
        results["cenario_2"] = await run_scenario_2_on_demand()
    except SmokeFailure as e:
        results["cenario_2"] = f"FALHA: {e}"
        print(str(e))
    
    try:
        results["cenario_3"] = await run_scenario_3_fallback()
    except SmokeFailure as e:
        results["cenario_3"] = f"FALHA: {e}"
        print(str(e))
    
    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    for name, result in results.items():
        status = "SUCESSO" if isinstance(result, dict) else result
        print(f"{name}: {status}")
    
    all_passed = all(isinstance(r, dict) for r in results.values())
    if all_passed:
        print("\nSMOKE TEST: TODOS OS CENARIOS PASSARAM")
        return 0
    else:
        print("\nSMOKE TEST: ALGUM CENARIO FALHOU")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_smoke())
    sys.exit(exit_code)
