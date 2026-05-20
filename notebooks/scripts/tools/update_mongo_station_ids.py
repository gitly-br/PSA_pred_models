"""Atualiza station_ids em floodcast.models conforme estacoes_bacia.json.

Idempotente: so atualiza se o array atual for diferente do esperado.
Nao altera active, is_champion, artifact_uri, thresholds, features, etc.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://psa:psa@localhost:16521/?authSource=admin")
DB_NAME = "floodcast"
COLLECTION_NAME = "models"
ESTACOES_PATH = Path(__file__).resolve().parents[3] / "notebooks" / "dados" / "estacoes_bacia.json"
REPORT_PATH = Path(__file__).resolve().parents[3] / "notebooks" / "dados" / "results" / "relatorio_mongo_station_ids_update.md"


def load_estacoes(path: Path) -> dict[str, list[str]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_current_docs(client: MongoClient) -> list[dict[str, Any]]:
    coll = client[DB_NAME][COLLECTION_NAME]
    projection = {
        "name": 1,
        "bacia": 1,
        "region": 1,
        "subregion": 1,
        "station_ids": 1,
        "is_champion": 1,
        "active": 1,
    }
    return list(coll.find({}, projection))


def update_station_ids(client: MongoClient, mapping: dict[str, list[str]]) -> dict[str, Any]:
    coll = client[DB_NAME][COLLECTION_NAME]
    before = fetch_current_docs(client)

    updated_count = 0
    skipped_count = 0
    missing_mapping = []
    failures = []
    updates_log = []

    for doc in before:
        bacia = doc.get("bacia", "")
        current = doc.get("station_ids", []) or []
        if bacia in mapping:
            expected = mapping[bacia]
            if current == expected:
                skipped_count += 1
                updates_log.append({
                    "name": doc.get("name"),
                    "bacia": bacia,
                    "action": "skipped",
                    "reason": "already correct",
                    "station_ids": expected,
                })
            else:
                try:
                    result = coll.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"station_ids": expected}},
                    )
                    if result.modified_count == 1:
                        updated_count += 1
                        updates_log.append({
                            "name": doc.get("name"),
                            "bacia": bacia,
                            "action": "updated",
                            "from_station_ids": current,
                            "to_station_ids": expected,
                        })
                    else:
                        skipped_count += 1
                        updates_log.append({
                            "name": doc.get("name"),
                            "bacia": bacia,
                            "action": "skipped",
                            "reason": "matched but not modified",
                            "station_ids": expected,
                        })
                except Exception as exc:
                    failures.append({"name": doc.get("name"), "bacia": bacia, "error": str(exc)})
        else:
            missing_mapping.append({"name": doc.get("name"), "bacia": bacia})

    after = fetch_current_docs(client)
    return {
        "before": before,
        "after": after,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "missing_mapping": missing_mapping,
        "failures": failures,
        "updates_log": updates_log,
        "mapping": mapping,
    }


def verify_after(after: list[dict[str, Any]], mapping: dict[str, list[str]]) -> list[dict[str, Any]]:
    mismatches = []
    for doc in after:
        bacia = doc.get("bacia", "")
        if bacia in mapping:
            expected = mapping[bacia]
            actual = doc.get("station_ids", []) or []
            if actual != expected:
                mismatches.append({
                    "name": doc.get("name"),
                    "bacia": bacia,
                    "expected": expected,
                    "actual": actual,
                })
    return mismatches


def generate_report(result: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc).isoformat()
    before = result["before"]
    after = result["after"]
    updated = result["updated_count"]
    skipped = result["skipped_count"]
    missing = result["missing_mapping"]
    failures = result["failures"]
    mapping = result["mapping"]
    mismatches = verify_after(after, mapping)

    lines = [
        "# Relatorio: Atualizacao de station_ids no MongoDB",
        "",
        f"- **Data/hora (UTC)**: {now}",
        f"- **Colecao**: `{DB_NAME}.{COLLECTION_NAME}`",
        f"- **URI**: `{MONGO_URI}`",
        "",
        "## Resumo",
        "",
        f"- Documentos encontrados antes: {len(before)}",
        f"- Documentos atualizados: {updated}",
        f"- Documentos ja corretos (skipped): {skipped}",
        f"- Bacias sem mapping: {len(missing)}",
        f"- Falhas durante update: {len(failures)}",
        f"- Divergencias apos update: {len(mismatches)}",
        "",
        "## Mapping utilizado (estacoes_bacia.json)",
        "",
        "| Bacia | Numero de estacoes |",
        "|-------|-------------------|",
    ]
    for bacia, stations in sorted(mapping.items()):
        lines.append(f"| {bacia} | {len(stations)} |")

    lines.extend([
        "",
        "## Estado antes do update",
        "",
        "| name | bacia | active | is_champion | station_ids (count) |",
        "|------|-------|--------|-------------|---------------------|",
    ])
    for doc in before:
        sids = doc.get("station_ids", []) or []
        lines.append(
            f"| {doc.get('name')} | {doc.get('bacia')} | {doc.get('active')} | {doc.get('is_champion')} | {len(sids)} |"
        )

    lines.extend([
        "",
        "## Estado apos o update",
        "",
        "| name | bacia | active | is_champion | station_ids (count) |",
        "|------|-------|--------|-------------|---------------------|",
    ])
    for doc in after:
        sids = doc.get("station_ids", []) or []
        lines.append(
            f"| {doc.get('name')} | {doc.get('bacia')} | {doc.get('active')} | {doc.get('is_champion')} | {len(sids)} |"
        )

    lines.extend([
        "",
        "## Detalhe das atualizacoes",
        "",
    ])
    for log in result["updates_log"]:
        action = log["action"]
        if action == "updated":
            lines.append(
                f"- **{log['name']}** ({log['bacia']}): atualizado de {log['from_station_ids']} para {log['to_station_ids']}"
            )
        else:
            lines.append(f"- **{log['name']}** ({log['bacia']}): {log['reason']}")

    if missing:
        lines.extend(["", "## Bacias sem mapping"])
        for m in missing:
            lines.append(f"- {m['name']} -> bacia='{m['bacia']}'")

    if failures:
        lines.extend(["", "## Falhas"])
        for f in failures:
            lines.append(f"- {f['name']} ({f['bacia']}): {f['error']}")

    if mismatches:
        lines.extend(["", "## Divergencias apos update (ERRO)"])
        for mm in mismatches:
            lines.append(f"- {mm['name']} ({mm['bacia']}): esperado {mm['expected']} vs atual {mm['actual']}")
    else:
        lines.extend(["", "## Verificacao pos-update", "", "Nenhuma divergencia encontrada."])

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    mapping = load_estacoes(ESTACOES_PATH)
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        report = (
            f"# Relatorio: Atualizacao de station_ids no MongoDB\n\n"
            f"**ERRO DE CONEXAO**: {type(exc).__name__}: {exc}\n\n"
            f"- MONGO_URI utilizado: `{MONGO_URI}`\n"
            f"- Verifique se o container MongoDB esta rodando e acessivel na porta 16521.\n"
            f"- Comando recomendado para verificar: `mongosh '{MONGO_URI}' --eval 'db.adminCommand({{ping:1}})'`\n"
        )
        REPORT_PATH.write_text(report, encoding="utf-8")
        print(f"FALHA DE CONEXAO. Relatorio salvo em: {REPORT_PATH}")
        raise SystemExit(1)

    result = update_station_ids(client, mapping)
    report_md = generate_report(result)
    REPORT_PATH.write_text(report_md, encoding="utf-8")
    print(f"Relatorio salvo em: {REPORT_PATH}")
    print(f"Documentos encontrados: {len(result['before'])}")
    print(f"Documentos atualizados: {result['updated_count']}")
    print(f"Documentos skipped: {result['skipped_count']}")
    print(f"Falhas: {len(result['failures'])}")
    print(f"Divergencias pos-update: {len(verify_after(result['after'], mapping))}")

    for bacia, stations in sorted(mapping.items()):
        print(f"Bacia {bacia}: {len(stations)} estacoes -> {stations}")

    if result["failures"] or verify_after(result["after"], mapping):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
