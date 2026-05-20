"""
Exporta os registros de validacao 2026 do Forms para Parquet.

Entrada:
  notebooks/dados/Feedback - Modelos de Predição de Alagamento (respostas) - Respostas ao formulário 1.csv

Saida:
  notebooks/dados/validacao/chamados_validacao_2026.parquet
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import polars as pl

WORKDIR = Path(__file__).resolve().parents[2]
DATA_DIR = WORKDIR / "dados"
SRC = DATA_DIR / "Feedback - Modelos de Predição de Alagamento (respostas) - Respostas ao formulário 1.csv"
OUT_DIR = DATA_DIR / "validacao"
OUT = OUT_DIR / "chamados_validacao_2026.parquet"
SRC_PARQUET = OUT
BACIAS_PATH = DATA_DIR / "bacias.json"


def _norm_text(expr: pl.Expr) -> pl.Expr:
    return (
        expr.cast(pl.Utf8)
        .str.strip_chars()
        .str.replace_all(r"\s+", " ")
    )


def _remover_acentos(txt: str | None) -> str | None:
    if txt is None:
        return None
    return "".join(c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c))


def _normalizar_bairro(nome: str | None) -> str | None:
    if nome is None:
        return None
    nome = _remover_acentos(nome).upper().strip()
    nome = " ".join(nome.split())
    for longo, curto in [
        ("VILA ", "VL "),
        ("JARDIM ", "JD "),
        ("PARQUE ", "PQ "),
        ("PRACA ", "PCA "),
        ("PRAÇA ", "PCA "),
    ]:
        if nome.startswith(longo):
            nome = curto + nome[len(longo):]
            break
    return {
        "PQ. NOVO ORATORIO": "PQ NOVO ORATORIO",
        "Pq. Novo Oratório": "PQ NOVO ORATORIO",
        "PARQUE NOVO ORATORIO": "PQ NOVO ORATORIO",
        "PARQUE DAS NACOES": "PQ DAS NACOES",
        "PARQUE DAS NAÇÕES": "PQ DAS NACOES",
        "JD. SANTO ANDRE": "JD SANTO ANDRE",
        "JARDIM SANTO ANDRE": "JD SANTO ANDRE",
        "UTINGA": "JD UTINGA",
        "CAPUAVA": "PQ CAPUAVA",
        "JARDIM STELLA": "JD STELLA",
        "VILA PALMARES": "VL PALMARES",
        "VILA SCARPELLI": "VL SCARPELLI",
        "VL GUIMAR": "VL GUIOMAR",
        "VL SANTO ALBERTO": "JD SANTO ALBERTO",
        "JARDIM SANTO ALBERTO": "JD SANTO ALBERTO",
        "BAIRRO JARDIM": "JD",
        "VL SILVEIRA": "SILVEIRA",
    }.get(nome, nome)


def main() -> None:
    if SRC.exists():
        df = pl.read_csv(SRC, infer_schema_length=1000, ignore_errors=True)
        df = df.rename({c: c.strip() for c in df.columns})
    elif SRC_PARQUET.exists():
        df = pl.read_parquet(SRC_PARQUET)
    else:
        raise FileNotFoundError(f"No input found at {SRC} or {SRC_PARQUET}")

    with BACIAS_PATH.open() as f:
        bacias_raw = json.load(f)
    bairro_to_bacia = {
        _normalizar_bairro(bairro): bacia
        for bacia, bairros in bacias_raw.items()
        for bairro in bairros
    }

    df = df.with_columns(
        _norm_text(pl.col("resposta_em_dt").cast(pl.Utf8) if "resposta_em_dt" in df.columns else pl.col("Carimbo de data/hora")).alias("resposta_em"),
        _norm_text(pl.col("data_ocorrencia").cast(pl.Utf8) if "data_ocorrencia" in df.columns else pl.col("Em qual dia ocorreu a inundação/alagamento que você está reportando?")).alias("data_ocorrencia_raw"),
    )

    if "resposta_em_dt" not in df.columns:
        df = df.with_columns(pl.col("resposta_em").str.to_datetime("%d/%m/%Y %H:%M:%S").alias("resposta_em_dt"))
    if "data_ocorrencia" not in df.columns:
        df = df.with_columns(pl.col("data_ocorrencia_raw").str.to_date("%d/%m/%Y").alias("data_ocorrencia"))

    if "periodo" not in df.columns:
        df = df.with_columns(_norm_text(pl.col("Qual o período da inundação/alagamento?")).alias("periodo"))
    if "bairro" not in df.columns:
        df = df.with_columns(_norm_text(pl.col("Qual o Bairro da ocorrência de  inundação/alagamento?")).alias("bairro"))
    if "cep" not in df.columns:
        df = df.with_columns(_norm_text(pl.col("Qual o CEP da ocorrência de  inundação/alagamento?")).alias("cep"))
    if "endereco" not in df.columns:
        df = df.with_columns(_norm_text(pl.col("Qual o Endereço (rua, número, referência) da ocorrência de inuncação/alagamento?")).alias("endereco"))
    if "intensidade_inundacao" not in df.columns:
        df = df.with_columns(_norm_text(pl.col("Qual a intensidade da inundação/alagamento?")).alias("intensidade_inundacao"))
    if "intensidade_chuva" not in df.columns:
        df = df.with_columns(_norm_text(pl.col("Qual a intensidade da chuva que causou este alagamento?")).alias("intensidade_chuva"))

    df_2026 = (
        df.filter(pl.col("data_ocorrencia").dt.year() == 2026)
        .select(
            [
                "resposta_em_dt",
                "data_ocorrencia",
                "periodo",
                "bairro",
                "cep",
                "endereco",
                "intensidade_inundacao",
                "intensidade_chuva",
            ]
        )
        .with_columns(
            pl.col("bairro").map_elements(_normalizar_bairro, return_dtype=pl.Utf8).alias("bairro_norm"),
        )
        .with_columns(
            pl.col("bairro_norm").map_elements(lambda x: bairro_to_bacia.get(x), return_dtype=pl.Utf8).alias("bacia")
        )
        .with_columns(
            # Ajustes confirmados por geocodificacao + sub-bacias.geojson.
            pl.when(pl.col("bairro_norm") == "VL SA")
            .then(pl.lit("oratorio"))
            .when(pl.col("bairro_norm") == "VL VILMA")
            .then(pl.lit("tamanduatei"))
            .otherwise(pl.col("bacia"))
            .alias("bacia")
        )
        .with_columns(
            (pl.col("bacia") == "guarara").fill_null(False).alias("bacia_guarara"),
            (pl.col("bacia") == "oratorio").fill_null(False).alias("bacia_oratorio"),
            (pl.col("bacia") == "meninos").fill_null(False).alias("bacia_meninos"),
            (pl.col("bacia") == "tamanduatei").fill_null(False).alias("bacia_tamanduatei"),
            pl.col("bacia").is_null().alias("bacia_desconhecida"),
        )
        .select(
            [
                "resposta_em_dt",
                "data_ocorrencia",
                "periodo",
                "bairro",
                "bairro_norm",
                "bacia",
                "bacia_guarara",
                "bacia_oratorio",
                "bacia_meninos",
                "bacia_tamanduatei",
                "bacia_desconhecida",
                "cep",
                "endereco",
                "intensidade_inundacao",
                "intensidade_chuva",
            ]
        )
        .sort(["data_ocorrencia", "resposta_em_dt", "bairro"])
        .with_columns(pl.lit("forms_feedback_predicao_alagamento").alias("fonte"))
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df_2026.write_parquet(OUT)
    print(f"salvo {OUT} com {df_2026.height} linhas")


if __name__ == "__main__":
    main()
