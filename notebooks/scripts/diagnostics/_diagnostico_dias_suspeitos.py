"""
D1 — Diagnóstico de dias suspeitos.

Hipótese: o target binário ("houve chamado") confunde "houve enchente"
com "alguém ligou". Dias com chuva idêntica a positivos podem estar
sendo rotulados como negativos por viés comportamental (fim de semana,
madrugada, bairros menos engajados).

Saída:
- `dados/_dias_suspeitos.parquet` — para cada dia (data, bacia) negativo,
  similaridade ao centróide dos positivos da bacia + flags contextuais.
- `dados/_target_enriquecido.parquet` — target consolidado:
  * positivo se chamado confirmado (V4) OU dia em alagamentos_bacias para bacia
  * suspeito se negativo + similaridade alta + (fim de semana OU madrugada OU chuva ≥ p90 dos positivos)
"""
import polars as pl
import numpy as np
import json
from datetime import datetime, date
from functools import reduce
from scipy.signal import lfilter
from scipy.spatial.distance import cdist

MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
JANELAS_H = [1, 3, 6, 24, 48, 72]
LIMS = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
LOOKBACK_H = 72
K_API = 0.85

# carrega base como o V4
with open("dados/estacoes_bacia.json") as f:
    estacoes_bacia = json.load(f)

partes = []
for bacia in estacoes_bacia:
    df = pl.read_parquet(f"dados/chuva_bacias/chuva_{bacia}.parquet")
    est_cols = [c for c in df.columns if c != "hora"]
    partes.append(
        df.with_columns([
            pl.max_horizontal(est_cols).alias("chuva_max_mm"),
            pl.mean_horizontal(est_cols).alias("chuva_mean_mm"),
            pl.sum_horizontal([(pl.col(c) > 1.0).cast(pl.Int8) for c in est_cols]).alias("n_chovendo"),
        ]).select(["hora", "chuva_max_mm", "chuva_mean_mm", "n_chovendo"])
        .with_columns(pl.lit(bacia).alias("bacia"))
    )
df_chuva_h = pl.concat(partes).sort(["bacia", "hora"])

# target original (V4): chamados confirmados
df_chamados_raw = pl.read_parquet("dados/chamados_por_bacia.parquet")
_chamados_idx = (
    df_chamados_raw.drop_nulls("dt_abertura").filter(pl.col("bacia").is_not_null())
    .with_row_index("_idx")
    .with_columns([
        (pl.col("dt_abertura") - pl.duration(hours=LOOKBACK_H)).alias("dt_inicio"),
        pl.col("dt_abertura").alias("dt_fim"),
    ]).rename({"bacia": "bacia_cham"})
)
_joined = (
    _chamados_idx.join_where(
        df_chuva_h.select(["hora", "chuva_max_mm", "bacia"]),
        pl.col("hora") >= pl.col("dt_inicio"),
        pl.col("hora") <= pl.col("dt_fim"),
    ).filter(pl.col("bacia_cham") == pl.col("bacia"))
    .select(["_idx", "hora", "chuva_max_mm"]).sort(["_idx", "hora"])
)
_accs = _chamados_idx.select("_idx")
for h in JANELAS_H:
    _sub = (_joined.rolling("hora", period=f"{h}h", group_by="_idx")
            .agg(pl.col("chuva_max_mm").sum().alias("acc"))
            .group_by("_idx").agg(pl.col("acc").max().alias(f"acc_{h}h")))
    _accs = _accs.join(_sub, on="_idx", how="left")
_cond = reduce(lambda a, b: a | b,
    [pl.col(f"acc_{h}h").fill_null(0) >= LIMS[h] for h in JANELAS_H])
df_chamados_conf = (
    df_chamados_raw.drop_nulls("dt_abertura").filter(pl.col("bacia").is_not_null())
    .with_row_index("_idx")
    .join(_accs, on="_idx", how="left").drop("_idx")
    .with_columns(_cond.alias("confirmado_chuva_bacia"))
    .filter(pl.col("confirmado_chuva_bacia"))
    .select(["dt_abertura", "bacia"])
)

# features diárias (subset do V4 — para similaridade)
df_h = df_chuva_h.with_columns(pl.col("hora").dt.date().alias("data"))
df_diario = (
    df_h.group_by(["data", "bacia"])
    .agg([
        pl.col("chuva_max_mm").max().alias("max_dia"),
        pl.col("chuva_max_mm").sum().alias("acum_dia"),
        pl.col("chuva_mean_mm").mean().alias("mean_dia"),
        pl.col("n_chovendo").max().alias("n_chovendo_max"),
        (pl.col("chuva_max_mm") >= 5.0).sum().alias("horas_intensas"),
    ]).sort(["bacia", "data"])
)
# api por bacia
api_parts = []
for b in df_diario["bacia"].unique().to_list():
    s = df_diario.filter(pl.col("bacia") == b).sort("data")
    v = s["max_dia"].fill_null(0).to_numpy()
    api = lfilter([1.0], [1.0, -K_API], v)
    api_parts.append(s.select(["data", "bacia"]).with_columns(pl.Series("api_085", api)))
df_diario = df_diario.join(pl.concat(api_parts), on=["data", "bacia"])

# target original
target_v4 = (
    df_chamados_conf.with_columns(pl.col("dt_abertura").dt.date().alias("data"))
    .group_by(["data", "bacia"]).len()
    .with_columns(pl.lit(True).alias("pos_chamado"))
    .select(["data", "bacia", "pos_chamado"])
)

# fontes externas (alagamentos_bacias.csv)
ext = pl.read_csv("dados/alagamentos_bacias.csv").with_columns(pl.col("dt").str.to_date())
ext_long = ext.select([
    pl.col("dt").alias("data"),
    pl.col("bacia_tamanduatei").alias("tamanduatei"),
    pl.col("bacia_guarara").alias("guarara"),
    pl.col("bacia_oratorio").alias("oratorio"),
    pl.col("bacia_meninos").alias("meninos"),
]).unpivot(index="data", variable_name="bacia", value_name="flag").filter(pl.col("flag") > 0).select(["data", "bacia"])
ext_long = ext_long.with_columns(pl.lit(True).alias("pos_externo"))

# calendário base
bacias = list(estacoes_bacia.keys())
datas = pl.date_range(date(2016, 1, 1), date(2025, 12, 31), interval="1d", eager=True).to_list()
cal = pl.DataFrame({
    "data": pl.Series([d for d in datas for _ in bacias], dtype=pl.Date),
    "bacia": [b for _ in datas for b in bacias],
})

df_full = (
    cal.join(target_v4, on=["data", "bacia"], how="left")
    .join(ext_long, on=["data", "bacia"], how="left")
    .with_columns([
        pl.col("pos_chamado").fill_null(False),
        pl.col("pos_externo").fill_null(False),
    ])
    .join(df_diario, on=["data", "bacia"], how="left")
    .filter(pl.col("data").dt.month().is_in(MESES_CHUVOSOS))
)

# ---- diagnóstico de similaridade por bacia ----
FEATS_SIM = ["max_dia", "acum_dia", "mean_dia", "n_chovendo_max", "horas_intensas", "api_085"]

print("=" * 90)
print(f"{'BACIA':<14} {'pos_cham':>9} {'pos_ext':>8} {'novos_ext':>10} {'neg_total':>10} {'suspeitos':>10}")
print("=" * 90)

linhas_susp = []
linhas_novos_pos = []

for b in bacias:
    sub = df_full.filter(pl.col("bacia") == b).drop_nulls(FEATS_SIM)
    pos_cham_mask = sub["pos_chamado"].to_numpy()
    pos_ext_mask = sub["pos_externo"].to_numpy()
    pos_any_mask = pos_cham_mask | pos_ext_mask
    novos = int(pos_ext_mask.sum() - (pos_cham_mask & pos_ext_mask).sum())

    X = sub.select(FEATS_SIM).to_numpy()
    # normalizar por desvio
    sd = X.std(axis=0) + 1e-9
    Xn = X / sd

    pos_idx = np.where(pos_any_mask)[0]
    neg_idx = np.where(~pos_any_mask)[0]
    if len(pos_idx) == 0 or len(neg_idx) == 0:
        continue

    # distância de cada negativo ao positivo mais próximo
    dists = cdist(Xn[neg_idx], Xn[pos_idx], metric="euclidean").min(axis=1)

    # limiar: percentil 50 das distâncias entre positivos (mediana intra-positivo)
    if len(pos_idx) > 1:
        dpos = cdist(Xn[pos_idx], Xn[pos_idx], metric="euclidean")
        np.fill_diagonal(dpos, np.inf)
        dpos_min = dpos.min(axis=1)
        thr_sim = float(np.median(dpos_min))
    else:
        thr_sim = 1.0

    suspeitos_mask = dists <= thr_sim

    # severidade da chuva no dia (max_dia ≥ p75 dos positivos)
    p75_max = float(np.percentile(X[pos_idx, 0], 75)) if len(pos_idx) > 0 else 0
    chuva_severa = X[neg_idx, 0] >= p75_max

    # contexto temporal (fim de semana, madrugada não temos por dia — só weekday)
    datas_neg = sub.filter(~pl.Series(pos_any_mask))["data"].to_list()
    weekday = np.array([d.weekday() for d in datas_neg])
    fim_de_semana = (weekday >= 5)

    # candidatos a "suspeito" = perto de positivo + (chuva severa OU fim de semana)
    cand = suspeitos_mask & (chuva_severa | fim_de_semana)

    print(f"{b:<14} {pos_cham_mask.sum():>9} {pos_ext_mask.sum():>8} {novos:>10} {len(neg_idx):>10} {cand.sum():>10}")

    # registrar
    sub_neg = sub.filter(~pl.Series(pos_any_mask))
    df_b = sub_neg.with_columns([
        pl.Series("dist_pos", dists),
        pl.Series("similar", suspeitos_mask),
        pl.Series("chuva_severa", chuva_severa),
        pl.Series("fim_semana", fim_de_semana),
        pl.Series("suspeito", cand),
    ]).filter(pl.col("suspeito"))
    linhas_susp.append(df_b.with_columns(pl.lit(b).alias("bacia_lab")))

    # registrar novos positivos via fonte externa (que não são chamado)
    novos_pos = sub.filter(pl.col("pos_externo") & ~pl.col("pos_chamado"))
    if novos_pos.height > 0:
        linhas_novos_pos.append(novos_pos.select(["data", "bacia", "max_dia", "acum_dia", "api_085"]))

if linhas_susp:
    df_susp = pl.concat(linhas_susp)
    df_susp.write_parquet("dados/_dias_suspeitos.parquet")
    print(f"\nSalvo: dados/_dias_suspeitos.parquet ({df_susp.height} linhas)")

if linhas_novos_pos:
    df_novos = pl.concat(linhas_novos_pos)
    print(f"\nNovos positivos via fonte externa (sem chamado): {df_novos.height}")
    print(df_novos.group_by("bacia").len().sort("bacia").to_pandas().to_string(index=False))
    df_novos.write_parquet("dados/_novos_positivos_externos.parquet")
    print("Salvo: dados/_novos_positivos_externos.parquet")
