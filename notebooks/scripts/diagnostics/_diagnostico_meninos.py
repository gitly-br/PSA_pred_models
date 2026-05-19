"""
Bloco B — revalidação programática das estações da bacia meninos.

Objetivo: aumentar taxa de confirmação por chuva dos chamados de meninos
(hoje 50.8%) sem inflar falsos positivos. Critério-alvo: ≥ 65%.

Método:
1. Para cada chamado da bacia meninos, computar quais estações CEMADEN
   confirmam chuva (qualquer janela [1,3,6,24,48,72]h ≥ LIMS) na janela
   72h retroativa ao dt_abertura.
2. Cobertura atual = chamados confirmados pela união das 8 estações
   atuais.
3. Greedy forward: adicionar estações (entre as 65 disponíveis no
   CEMADEN) que mais aumentam cobertura, restringindo a estações dentro
   de raio plausível (3 km do centróide dos chamados de meninos).
4. Reportar: cobertura por configuração; estações sugeridas para adição.
"""

import polars as pl
import json
import numpy as np
from functools import reduce
from math import radians, cos, sin, asin, sqrt

JANELAS_H = [1, 3, 6, 24, 48, 72]
LIMS      = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
LOOKBACK_H = 72
RAIO_KM   = 8.0

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2 * R * asin(sqrt(a))


with open("dados/estacoes_bacia.json") as f:
    estacoes_bacia = json.load(f)
ESTACOES_ATUAL = set(estacoes_bacia["meninos"])

cem = pl.read_parquet("dados/cemaden_abcd.parquet")
estacoes_meta = (
    cem.group_by("codEstacao")
    .agg([pl.col("latitude").first(), pl.col("longitude").first(),
          pl.col("nomeEstacao").first(), pl.col("municipio").first()])
)

cham = (
    pl.read_parquet("dados/chamados_por_bacia.parquet")
    .filter(pl.col("bacia") == "meninos")
    .drop_nulls(["dt_abertura", "latitude", "longitude"])
    .with_row_index("_idx")
)
print(f"Chamados meninos: {cham.height}")

cent_lat = float(cham["latitude"].mean())
cent_lon = float(cham["longitude"].mean())
print(f"Centróide chamados meninos: lat={cent_lat:.4f} lon={cent_lon:.4f}")

estacoes_proximas = []
for r in estacoes_meta.iter_rows(named=True):
    d = haversine(cent_lat, cent_lon, r["latitude"], r["longitude"])
    estacoes_proximas.append({
        "codEstacao": r["codEstacao"], "nome": r["nomeEstacao"],
        "municipio": r["municipio"], "dist_km": d,
        "atual": r["codEstacao"] in ESTACOES_ATUAL,
    })
df_est = pl.DataFrame(estacoes_proximas).sort("dist_km")
print("\nEstações por distância ao centróide (top 20):")
print(df_est.head(20).to_pandas().to_string(index=False))

cands = df_est.filter(pl.col("dist_km") <= RAIO_KM)["codEstacao"].to_list()
todas = sorted(set(cands) | ESTACOES_ATUAL)
print(f"\n{len(todas)} estações candidatas (raio {RAIO_KM}km + atuais).")

cem_cand = (
    cem.filter(pl.col("codEstacao").is_in(todas))
    .with_columns(pl.col("dt").dt.truncate("1h").alias("hora"))
    .group_by(["codEstacao", "hora"])
    .agg(pl.col("valor_mm").sum().alias("mm"))
    .sort(["codEstacao", "hora"])
)

cham_idx = cham.with_columns([
    (pl.col("dt_abertura") - pl.duration(hours=LOOKBACK_H)).alias("dt_inicio"),
    pl.col("dt_abertura").alias("dt_fim"),
]).select(["_idx", "dt_inicio", "dt_fim"])

confirma = {}
for est in todas:
    serie = cem_cand.filter(pl.col("codEstacao") == est).select(["hora", "mm"])
    if serie.height == 0:
        confirma[est] = np.zeros(cham.height, dtype=bool)
        continue
    j = (
        cham_idx.join_where(serie,
            pl.col("hora") >= pl.col("dt_inicio"),
            pl.col("hora") <= pl.col("dt_fim"))
        .select(["_idx", "hora", "mm"])
        .sort(["_idx", "hora"])
    )
    accs = cham_idx.select("_idx")
    for h in JANELAS_H:
        sub = (
            j.rolling("hora", period=f"{h}h", group_by="_idx")
            .agg(pl.col("mm").sum().alias("acc"))
            .group_by("_idx").agg(pl.col("acc").max().alias(f"acc_{h}h"))
        )
        accs = accs.join(sub, on="_idx", how="left")
    cond = reduce(lambda a, b: a | b,
        [pl.col(f"acc_{h}h").fill_null(0) >= LIMS[h] for h in JANELAS_H])
    flag = (
        accs.with_columns(cond.alias("conf")).sort("_idx")["conf"].to_numpy()
    )
    confirma[est] = flag

n_cham = cham.height

def cobertura(estacoes_set):
    if not estacoes_set:
        return 0.0
    m = np.zeros(n_cham, dtype=bool)
    for e in estacoes_set:
        m |= confirma[e]
    return m.mean()

print(f"\nCobertura ATUAL (8 estações): {cobertura(ESTACOES_ATUAL):.1%}")
todas_set = set(todas)
print(f"Cobertura MÁX (todas {len(todas_set)} candidatas): {cobertura(todas_set):.1%}")

print("\nCobertura individual de cada estação candidata:")
linhas = []
for e in todas:
    cov_indiv = confirma[e].mean()
    linhas.append({
        "codEstacao": e,
        "atual": e in ESTACOES_ATUAL,
        "cov_individual": round(cov_indiv, 3),
    })
df_cov_ind = pl.DataFrame(linhas).join(df_est.select(["codEstacao", "nome", "dist_km"]), on="codEstacao", how="left").sort("cov_individual", descending=True)
print(df_cov_ind.to_pandas().to_string(index=False))

print("\nGreedy forward: adicionar estações que mais aumentam cobertura.")
sel = set(ESTACOES_ATUAL)
cov = cobertura(sel)
print(f"Inicial (atuais): {cov:.1%}")
historico = [{"passo": 0, "adicionada": "(atuais)", "cobertura": round(cov, 3), "n_estacoes": len(sel)}]
restantes = todas_set - sel
passo = 0
while restantes:
    melhor, melhor_cov = None, cov
    for e in restantes:
        c = cobertura(sel | {e})
        if c > melhor_cov:
            melhor_cov, melhor = c, e
    if melhor is None or melhor_cov - cov < 0.01:
        break
    passo += 1
    sel.add(melhor)
    restantes.remove(melhor)
    cov = melhor_cov
    historico.append({"passo": passo, "adicionada": melhor,
                      "cobertura": round(cov, 3), "n_estacoes": len(sel)})
    if cov >= 0.85:
        break

print("\nHistórico de adição (ganho ≥ 1pp):")
print(pl.DataFrame(historico).to_pandas().to_string(index=False))

print(f"\nConfiguração final: {len(sel)} estações, cobertura {cov:.1%}")
print("Adicionadas:", sorted(sel - ESTACOES_ATUAL))
print("Mantidas:", sorted(ESTACOES_ATUAL & sel))
print("Removidas:", sorted(ESTACOES_ATUAL - sel))

with open("dados/_meninos_revalidacao.json", "w") as f:
    json.dump({
        "atual": sorted(ESTACOES_ATUAL),
        "sugerida": sorted(sel),
        "cobertura_atual": round(cobertura(ESTACOES_ATUAL), 3),
        "cobertura_sugerida": round(cov, 3),
        "raio_km": RAIO_KM,
        "historico": historico,
    }, f, indent=2)
print("\nSalvo em dados/_meninos_revalidacao.json")
