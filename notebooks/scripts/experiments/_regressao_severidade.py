"""
Experimento: Regressão direta de severidade (0-3) como valor contínuo.

- Usa a MESMA feature engineering do benchmark_v8 (leak corrigido).
- Treina um único regressor (GradientBoostingRegressor e LGBMRegressor).
- Deriva probabilidade de evento (severidade >= 1) via normalização do output.
- Avalia duas estratégias de normalização.
"""

import json
import sys
import warnings
from datetime import date, datetime
from functools import reduce
from pathlib import Path

import numpy as np
import polars as pl
from scipy.signal import lfilter
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import (
    average_precision_score, f1_score, precision_score, recall_score,
)
from sklearn.model_selection import TimeSeriesSplit

from lightgbm import LGBMRegressor

WORKDIR = Path(__file__).resolve().parents[2]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)

# ─── Config (mesmo do benchmark_v8) ───────────────────────────────────────
MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
JANELAS_H = [1, 3, 6, 24, 48, 72]
LIMS = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
LOOKBACK_H = 72
T_CUT = datetime(2023, 7, 2).date()
K_APIS = [0.70, 0.85, 0.95]
LIM_INTENSO_MM = 5.0

FEATURES = (
    [f"api_{int(k*100):03d}" for k in K_APIS]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]
)


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


# ─── Feature Engineering (idêntica ao benchmark_v8) ──────────────────────

def build_dataset():
    with open(WORKDIR / "dados" / "estacoes_bacia.json") as f:
        estacoes_bacia = json.load(f)

    partes = []
    for bacia in estacoes_bacia:
        df = pl.read_parquet(WORKDIR / "dados" / "chuva_bacias" / f"chuva_{bacia}.parquet")
        est_cols = [c for c in df.columns if c != "hora"]
        partes.append(
            df.with_columns([
                pl.max_horizontal(est_cols).alias("chuva_max_mm"),
                pl.mean_horizontal(est_cols).alias("chuva_mean_mm"),
                pl.concat_list(est_cols).list.std().alias("chuva_std_mm"),
                pl.sum_horizontal([(pl.col(c) > 1.0).cast(pl.Int8) for c in est_cols]).alias("n_chovendo"),
            ])
            .select(["hora", "chuva_max_mm", "chuva_mean_mm", "chuva_std_mm", "n_chovendo"])
            .with_columns(pl.lit(bacia).alias("bacia"))
        )
    df_chuva_h = pl.concat(partes).sort(["bacia", "hora"])

    # confirmados por chuva na bacia
    df_chamados_raw = pl.read_parquet(WORKDIR / "dados" / "chamados_por_bacia.parquet")
    _chamados_idx = (
        df_chamados_raw.drop_nulls("dt_abertura").filter(pl.col("bacia").is_not_null())
        .with_row_index("_idx")
        .with_columns([
            (pl.col("dt_abertura") - pl.duration(hours=LOOKBACK_H)).alias("dt_inicio"),
            pl.col("dt_abertura").alias("dt_fim"),
        ])
        .rename({"bacia": "bacia_cham"})
    )
    _joined = (
        _chamados_idx.join_where(df_chuva_h,
            pl.col("hora") >= pl.col("dt_inicio"),
            pl.col("hora") <= pl.col("dt_fim"),
        )
        .filter(pl.col("bacia_cham") == pl.col("bacia"))
        .select(["_idx", "hora", "chuva_max_mm"]).sort(["_idx", "hora"])
    )
    _accs = _chamados_idx.select("_idx")
    for h in JANELAS_H:
        _sub = (
            _joined.rolling("hora", period=f"{h}h", group_by="_idx")
            .agg(pl.col("chuva_max_mm").sum().alias("acc"))
            .group_by("_idx").agg(pl.col("acc").max().alias(f"acc_{h}h"))
        )
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

    # diários
    df_h = df_chuva_h.with_columns([
        pl.col("hora").dt.date().alias("data"),
        (pl.col("hora").dt.hour() // 6).alias("bloco_6h"),
    ])
    df_blocos = (
        df_h.group_by(["data", "bacia", "bloco_6h"])
        .agg(pl.col("chuva_max_mm").sum().alias("acc_6h"))
        .sort(["bacia", "data", "bloco_6h"])
    )
    df_blocos_wide = (
        df_blocos
        .with_columns(pl.concat_str([pl.lit("bloco_"), pl.col("bloco_6h").cast(pl.Utf8)]).alias("col"))
        .pivot(on="col", index=["data", "bacia"], values="acc_6h", aggregate_function="first")
        .sort(["bacia", "data"])
        .with_columns([pl.col(c).fill_null(0) for c in ["bloco_0","bloco_1","bloco_2","bloco_3"]])
    )
    df_diario = (
        df_h.group_by(["data", "bacia"])
        .agg([
            pl.col("chuva_max_mm").max().alias("max_dia"),
            pl.col("chuva_max_mm").sum().alias("acum_dia"),
            pl.col("chuva_mean_mm").mean().alias("mean_dia"),
            pl.col("chuva_std_mm").mean().alias("std_dia"),
            pl.col("n_chovendo").max().alias("n_chovendo_max"),
            pl.col("chuva_max_mm").max().alias("pico_1h"),
            (pl.col("chuva_max_mm") >= LIM_INTENSO_MM).sum().alias("horas_intensas"),
        ])
        .sort(["bacia", "data"])
    )
    df_feat = (
        df_blocos_wide.join(df_diario, on=["data", "bacia"])
        .with_columns([
            pl.col("bloco_0").shift(3).over("bacia").alias("acc_6h_lag_1"),
            pl.col("bloco_1").shift(3).over("bacia").alias("acc_6h_lag_2"),
            pl.col("bloco_2").shift(3).over("bacia").alias("acc_6h_lag_3"),
            pl.col("bloco_3").shift(3).over("bacia").alias("acc_6h_lag_4"),
            pl.col("bloco_0").shift(2).over("bacia").alias("acc_6h_lag_5"),
            pl.col("bloco_1").shift(2).over("bacia").alias("acc_6h_lag_6"),
            pl.col("bloco_2").shift(2).over("bacia").alias("acc_6h_lag_7"),
            pl.col("bloco_3").shift(2).over("bacia").alias("acc_6h_lag_8"),
            pl.col("bloco_0").shift(1).over("bacia").alias("acc_6h_lag_9"),
            pl.col("bloco_1").shift(1).over("bacia").alias("acc_6h_lag_10"),
            pl.col("bloco_2").shift(1).over("bacia").alias("acc_6h_lag_11"),
            pl.col("bloco_3").shift(1).over("bacia").alias("acc_6h_lag_12"),
            pl.col("max_dia").shift(1).over("bacia").alias("max_day_lag1"),
            pl.col("max_dia").shift(2).over("bacia").alias("max_day_lag2"),
            pl.col("max_dia").shift(3).over("bacia").alias("max_day_lag3"),
            pl.col("mean_dia").shift(1).over("bacia").alias("mean_day_lag1"),
            pl.col("std_dia").shift(1).over("bacia").alias("std_day_lag1"),
            pl.col("n_chovendo_max").shift(1).over("bacia").alias("n_chovendo_max_lag1"),
            pl.col("pico_1h").shift(1).over("bacia").alias("pico_1h_lag1"),
            pl.col("horas_intensas").shift(1).over("bacia").alias("horas_intensas_lag1"),
            pl.col("acum_dia").rolling_sum(window_size=7, min_samples=1).shift(1).over("bacia").alias("acum_7d"),
            pl.col("acum_dia").rolling_sum(window_size=30, min_samples=1).shift(1).over("bacia").alias("acum_30d"),
            (2 * np.pi * pl.col("data").dt.month() / 12).sin().alias("mes_sin"),
            (2 * np.pi * pl.col("data").dt.month() / 12).cos().alias("mes_cos"),
        ])
    )

    # API com leak corrigido
    _api_parts = []
    for _bacia in df_diario["bacia"].unique().to_list():
        _sub = df_diario.filter(pl.col("bacia") == _bacia).sort("data")
        _vals = _sub["max_dia"].shift(1).fill_null(0).to_numpy()
        cols = {"data": _sub["data"], "bacia": _sub["bacia"]}
        for _k in K_APIS:
            cols[f"api_{int(_k*100):03d}"] = lfilter([1.0], [1.0, -_k], _vals)
        _api_parts.append(pl.DataFrame(cols))
    df_api = pl.concat(_api_parts)

    df_feat = df_feat.join(df_api, on=["data", "bacia"])
    df_feat = df_feat.select(["data", "bacia"] + FEATURES)

    # Target ordinal
    _chamados_diario = (
        df_chamados_conf
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .group_by(["data","bacia"]).len().rename({"len":"n_chamados"})
    )
    _ext = pl.read_csv(WORKDIR / "dados" / "alagamentos_bacias.csv").with_columns(pl.col("dt").str.to_date())
    _df_ext = _ext.select([
        pl.col("dt").alias("data"),
        pl.col("bacia_tamanduatei").alias("tamanduatei"),
        pl.col("bacia_guarara").alias("guarara"),
        pl.col("bacia_oratorio").alias("oratorio"),
        pl.col("bacia_meninos").alias("meninos"),
    ]).unpivot(index="data", variable_name="bacia", value_name="flag").filter(pl.col("flag") > 0).select([
        "data","bacia", pl.lit(True).alias("pos_externo"),
    ])

    _bacias = list(estacoes_bacia.keys())
    _datas = pl.date_range(date(2016,1,1), date(2025,12,31), interval="1d", eager=True).to_list()
    _cal = pl.DataFrame({
        "data": pl.Series([d for d in _datas for _ in _bacias], dtype=pl.Date),
        "bacia": [b for _ in _datas for b in _bacias],
    })
    _max_dia = df_diario.select(["data","bacia","max_dia"])
    _chamados_max = _chamados_diario.join(_max_dia, on=["data","bacia"], how="left").filter(pl.col("data") < T_CUT)
    P50_BY_BACIA = {}
    for _b in _bacias:
        _s = _chamados_max.filter(pl.col("bacia") == _b)
        P50_BY_BACIA[_b] = float(_s["max_dia"].quantile(0.5)) if _s.height > 0 else 95.0

    df_ml = (
        _cal
        .join(_chamados_diario, on=["data","bacia"], how="left")
        .join(_df_ext, on=["data","bacia"], how="left")
        .join(_max_dia, on=["data","bacia"], how="left")
        .with_columns([
            pl.col("n_chamados").fill_null(0),
            pl.col("pos_externo").fill_null(False),
        ])
    )
    _p50_expr = pl.col("bacia").replace_strict(P50_BY_BACIA, return_dtype=pl.Float64)
    df_ml = df_ml.with_columns(
        pl.when((pl.col("n_chamados") >= 5) | pl.col("pos_externo")).then(3)
        .when(pl.col("n_chamados").is_between(2,4)).then(2)
        .when((pl.col("n_chamados") == 1) | ((pl.col("n_chamados") == 0) & (pl.col("max_dia") > _p50_expr))).then(1)
        .otherwise(0)
        .alias("severidade")
    )
    df_ml = df_ml.join(df_feat, on=["data","bacia"], how="left").filter(
        pl.col("data").dt.month().is_in(MESES_CHUVOSOS)
    ).sort(["bacia","data"])

    return df_ml, estacoes_bacia, P50_BY_BACIA


def calc_metrics(y_true_sev, prob_evento, threshold=0.5):
    y_bin = (y_true_sev >= 1).astype(int)
    prauc = average_precision_score(y_bin, prob_evento) if y_bin.sum() > 0 else 0.0
    pred_bin = (prob_evento >= threshold).astype(int)
    rec = recall_score(y_bin, pred_bin, zero_division=0)
    prec = precision_score(y_bin, pred_bin, zero_division=0)
    f1 = f1_score(y_bin, pred_bin, zero_division=0)
    return {"prauc": prauc, "recall": rec, "prec": prec, "f1": f1}


def avaliar_bacia_regressao(bacia, sub, modelos_dict):
    t_cut_local = T_CUT
    if bacia == "oratorio":
        ev = sub.filter(pl.col("enchente"))["data"].sort() if "enchente" in sub.columns else sub.filter(pl.col("severidade") >= 1)["data"].sort()
        if len(ev) > 0:
            t_cut_local = ev[int(len(ev)*0.75)]

    sub = sub.sort("data")
    train_all = sub.filter(pl.col("data") < t_cut_local)
    test = sub.filter(pl.col("data") >= t_cut_local)

    if train_all.height < 30 or test.height < 5:
        return None

    n_train = train_all.height
    split_idx = int(n_train * 0.75)
    train = train_all[:split_idx]
    val_holdout = train_all[split_idx:]

    X_train = train[FEATURES].to_pandas()
    X_val = val_holdout[FEATURES].to_pandas()
    X_test = test[FEATURES].to_pandas()
    sev_train = train["severidade"].to_numpy()
    sev_val = val_holdout["severidade"].to_numpy()
    sev_test = test["severidade"].to_numpy()

    # sample weights
    weight_map = {0: 1.0, 1: 2.0, 2: 4.0, 3: 8.0}
    sw_train = np.array([weight_map[int(s)] for s in sev_train], dtype=float)
    sw_val = np.array([weight_map[int(s)] for s in sev_val], dtype=float)

    results = {}
    for nome, mk_reg in modelos_dict.items():
        row = {"bacia": bacia, "modelo": nome}
        row["train_n"] = len(sev_train)
        row["val_n"] = len(sev_val)
        row["test_n"] = len(sev_test)
        row["sev_dist_train"] = {int(s): int((sev_train==s).sum()) for s in [0,1,2,3]}
        row["sev_dist_test"] = {int(s): int((sev_test==s).sum()) for s in [0,1,2,3]}

        # tuning de threshold no val_holdout via TimeSeriesSplit no train
        tscv = TimeSeriesSplit(n_splits=5)
        oof = np.full(len(sev_train), np.nan)
        for tr_i, va_i in tscv.split(X_train):
            if (sev_train[tr_i] >= 1).sum() == 0 or (sev_train[va_i] >= 1).sum() == 0:
                continue
            reg = mk_reg()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                reg.fit(X_train.iloc[tr_i], sev_train[tr_i], sample_weight=sw_train[tr_i])
            oof[va_i] = reg.predict(X_train.iloc[va_i])

        mask_oof = ~np.isnan(oof)
        # Threshold tuning usando estratégia linear no oof
        if mask_oof.sum() > 0 and (sev_train[mask_oof] >= 1).sum() > 0:
            prob_oof = np.clip(oof[mask_oof] / 2.0, 0.0, 1.0)
            # melhor threshold para F1 no oof (usando estratégia linear)
            from sklearn.metrics import precision_recall_curve
            prec, rec, thrs = precision_recall_curve((sev_train[mask_oof] >= 1).astype(int), prob_oof)
            f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
            best_thr = float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5
        else:
            best_thr = 0.5
        row["thr_tuned"] = best_thr

        # modelo final treinado em TODO train
        reg = mk_reg()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reg.fit(X_train, sev_train, sample_weight=sw_train)

        # predições
        pred_val = reg.predict(X_val)
        pred_test = reg.predict(X_test)

        # Estratégia 1: linear clamp output/2
        prob_val_lin = np.clip(pred_val / 2.0, 0.0, 1.0)
        prob_test_lin = np.clip(pred_test / 2.0, 0.0, 1.0)

        # Estratégia 2: sigmoid
        prob_val_sig = sigmoid((pred_val - 0.5) * 2.0)
        prob_test_sig = sigmoid((pred_test - 0.5) * 2.0)

        # Métricas val_holdout
        for estrat, prob_v, prob_t in [
            ("linear", prob_val_lin, prob_test_lin),
            ("sigmoid", prob_val_sig, prob_test_sig),
        ]:
            m_val = calc_metrics(sev_val, prob_v, threshold=best_thr)
            m_test = calc_metrics(sev_test, prob_t, threshold=0.5)
            for k, v in m_val.items():
                row[f"{k}_val_{estrat}"] = v
            for k, v in m_test.items():
                row[f"{k}_test_{estrat}"] = v

        # Spearman entre max_dia e prob_evento (val_holdout) — usando estratégia linear
        max_dia_val = val_holdout["max_dia"].to_numpy()
        corr, pval = spearmanr(max_dia_val, prob_val_lin)
        row["spearman_rho"] = float(corr)
        row["spearman_p"] = float(pval)

        # Também guardar predições brutas para análise
        row["pred_test_mean"] = float(np.mean(pred_test))
        row["pred_test_std"] = float(np.std(pred_test))
        row["pred_test_min"] = float(np.min(pred_test))
        row["pred_test_max"] = float(np.max(pred_test))

        results[nome] = row

    return results


def main():
    print("Building dataset with leak-corrected api_* ...")
    df_ml, estacoes_bacia, p50 = build_dataset()

    if "enchente" not in df_ml.columns:
        df_ml = df_ml.with_columns((pl.col("severidade") >= 1).alias("enchente"))

    modelos = {
        "GradBoostReg": lambda: GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.05,
            max_depth=2, min_samples_leaf=10,
            subsample=0.8, max_features="sqrt",
            random_state=42,
        ),
        "LGBMReg": lambda: LGBMRegressor(
            n_estimators=200, learning_rate=0.05,
            max_depth=2, num_leaves=8,
            min_child_samples=10, subsample=0.8,
            colsample_bytree=0.8, random_state=42,
            verbose=-1,
        ),
    }

    todos = []
    for bacia in sorted(estacoes_bacia.keys()):
        sub = df_ml.filter(pl.col("bacia") == bacia).drop_nulls(FEATURES)
        r = avaliar_bacia_regressao(bacia, sub, modelos)
        if r is None:
            print(f"  {bacia}: pulado (dados insuficientes)")
            continue
        for nome, row in r.items():
            todos.append(row)
        print(f"\n{'='*80}")
        print(f"  {bacia.upper()} (train_n={r[nome]['train_n']}, val_n={r[nome]['val_n']}, test_n={r[nome]['test_n']})")
        print(f"  Severidade train: {r[nome]['sev_dist_train']}")
        print(f"  Severidade test:  {r[nome]['sev_dist_test']}")
        print(f"\n  Validação holdout:")
        print(f"  {'Modelo':<12}  {'Estrat':<8}  {'PRAUC':>6}  {'Recall':>7}  {'Prec':>6}  {'F1':>5}  {'Spearman ρ':>10}")
        for nome, row in r.items():
            for estrat in ["linear", "sigmoid"]:
                print(f"  {nome:<12}  {estrat:<8}  "
                      f"{row[f'prauc_val_{estrat}']:>6.3f}  "
                      f"{row[f'recall_val_{estrat}']:>7.3f}  "
                      f"{row[f'prec_val_{estrat}']:>6.3f}  "
                      f"{row[f'f1_val_{estrat}']:>5.3f}  "
                      f"{row['spearman_rho']:>10.3f}")
        print(f"\n  Test set:")
        print(f"  {'Modelo':<12}  {'Estrat':<8}  {'PRAUC':>6}  {'Recall':>7}  {'Prec':>6}  {'F1':>5}  {'Thr':>5}")
        for nome, row in r.items():
            for estrat in ["linear", "sigmoid"]:
                print(f"  {nome:<12}  {estrat:<8}  "
                      f"{row[f'prauc_test_{estrat}']:>6.3f}  "
                      f"{row[f'recall_test_{estrat}']:>7.3f}  "
                      f"{row[f'prec_test_{estrat}']:>6.3f}  "
                      f"{row[f'f1_test_{estrat}']:>5.3f}  "
                      f"{row['thr_tuned']:>5.3f}")
        print(f"\n  Pred stats test (output bruto): mean={row['pred_test_mean']:.3f}, std={row['pred_test_std']:.3f}, min={row['pred_test_min']:.3f}, max={row['pred_test_max']:.3f}")

    import pandas as pd
    df_res = pd.DataFrame(todos)
    for col in ["sev_dist_train", "sev_dist_test"]:
        df_res[col] = df_res[col].apply(lambda d: str({str(k): v for k, v in d.items()}))
    out_path = OUT_DIR / "regressao_severidade.parquet"
    df_res.to_parquet(out_path)
    print(f"\nResultados salvos em {out_path}")
    print(df_res.to_string(index=False))


if __name__ == "__main__":
    main()
