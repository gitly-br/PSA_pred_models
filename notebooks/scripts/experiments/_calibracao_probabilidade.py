"""
Calibração de Probabilidade — Benchmark V8 + Isotonic.

Replica a feature engineering e o pipeline do benchmark_v8,
mas aplica CalibratedClassifierCV(method='isotonic') em cada um
dos 3 classificadores binários da cascata. Compara métricas com
o baseline não calibrado.
"""

import json
import warnings
from datetime import date, datetime
from functools import reduce
from pathlib import Path

import numpy as np
import polars as pl
from scipy.signal import lfilter
from scipy.stats import spearmanr
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

WORKDIR = Path(__file__).resolve().parents[2]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)

# ─── Config ──────────────────────────────────────────────────────────────
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


# ─── Feature Engineering (idêntica ao benchmark_v8) ─────────────────────

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

    # ── API com leak corrigido (shift(1) antes do lfilter) ──
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

    # ── Target ordinal ──
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


# ─── Helpers ─────────────────────────────────────────────────────────────

def _thr_f1(y_true, y_prob):
    from sklearn.metrics import precision_recall_curve
    prec, rec, thrs = precision_recall_curve(y_true, y_prob)
    if len(thrs) == 0:
        return 0.5
    f1s = (2*prec[:-1]*rec[:-1]) / (prec[:-1]+rec[:-1]+1e-9)
    return float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5


def _fit_with_sw(clf, X, y, sw):
    if isinstance(clf, Pipeline):
        clf.fit(X, y, clf__sample_weight=sw)
    else:
        clf.fit(X, y, sample_weight=sw)
    return clf


def mk_gradboost():
    return GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05,
        max_depth=2, min_samples_leaf=10,
        subsample=0.8, max_features="sqrt",
        random_state=42,
    )


def w_fit_m3(sev):
    return np.where(sev == 3, 3.0,
           np.where(sev == 2, 1.5,
           np.where(sev == 1, 1.0, 1.0)))


def train_and_eval(bacia, sub):
    t_cut_local = T_CUT
    if bacia == "oratorio":
        ev = sub.filter(pl.col("enchente"))["data"].sort()
        if len(ev) > 0:
            t_cut_local = ev[int(len(ev)*0.75)]

    sub = sub.sort("data")
    train_all = sub.filter(pl.col("data") < t_cut_local)
    test = sub.filter(pl.col("data") >= t_cut_local)

    if train_all.height < 30 or test.height < 5:
        return None

    # Holdout: últimos 25% do treino
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

    result = {"bacia": bacia}
    result["train_n"] = len(sev_train)
    result["val_n"] = len(sev_val)
    result["test_n"] = len(sev_test)
    result["sev_dist_train"] = {int(s): int((sev_train==s).sum()) for s in [0,1,2,3]}
    result["sev_dist_test"] = {int(s): int((sev_test==s).sum()) for s in [0,1,2,3]}

    # Treina baseline e calibrado para cada k
    for k in [1, 2, 3]:
        y_bin_train = (sev_train >= k).astype(int)
        y_bin_val = (sev_val >= k).astype(int)
        y_bin_test = (sev_test >= k).astype(int)

        if y_bin_train.sum() < 2 or y_bin_val.sum() == 0:
            for prefix in ["base", "cal"]:
                for metric in ["prauc", "recall", "prec", "f1"]:
                    result[f"{prefix}_test_k{k}_{metric}"] = 0.0
            result[f"base_test_k{k}_thr"] = 1.5
            result[f"cal_test_k{k}_thr"] = 1.5
            continue

        sw_train = w_fit_m3(sev_train).astype(float) if k == 3 else np.ones(len(sev_train), dtype=float)

        # ── Baseline ──
        clf_base = mk_gradboost()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _fit_with_sw(clf_base, X_train, y_bin_train, sw_train)

        prob_val_base = clf_base.predict_proba(X_val)[:, 1]
        thr_base = _thr_f1(y_bin_val, prob_val_base)
        prob_test_base = clf_base.predict_proba(X_test)[:, 1]
        alarme_test_base = (prob_test_base >= thr_base).astype(int)

        result[f"base_test_k{k}_thr"] = float(thr_base)
        result[f"base_test_k{k}_prauc"] = float(average_precision_score(y_bin_test, prob_test_base)) if y_bin_test.sum() > 0 else 0.0
        result[f"base_test_k{k}_recall"] = float(recall_score(y_bin_test, alarme_test_base, zero_division=0)) if y_bin_test.sum() > 0 else 0.0
        result[f"base_test_k{k}_prec"] = float(precision_score(y_bin_test, alarme_test_base, zero_division=0)) if y_bin_test.sum() > 0 else 0.0
        result[f"base_test_k{k}_f1"] = float(f1_score(y_bin_test, alarme_test_base, zero_division=0)) if y_bin_test.sum() > 0 else 0.0

        # ── Calibrado (Isotonic manual, equivalente a CalibratedClassifierCV cv='prefit') ──
        prob_val_cal_raw = clf_base.predict_proba(X_val)[:, 1]
        iso = IsotonicRegression(out_of_bounds="clip")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            iso.fit(prob_val_cal_raw, y_bin_val)
        prob_val_cal = iso.predict(prob_val_cal_raw)
        thr_cal = _thr_f1(y_bin_val, prob_val_cal)
        prob_test_cal = iso.predict(clf_base.predict_proba(X_test)[:, 1])
        alarme_test_cal = (prob_test_cal >= thr_cal).astype(int)

        result[f"cal_test_k{k}_thr"] = float(thr_cal)
        result[f"cal_test_k{k}_prauc"] = float(average_precision_score(y_bin_test, prob_test_cal)) if y_bin_test.sum() > 0 else 0.0
        result[f"cal_test_k{k}_recall"] = float(recall_score(y_bin_test, alarme_test_cal, zero_division=0)) if y_bin_test.sum() > 0 else 0.0
        result[f"cal_test_k{k}_prec"] = float(precision_score(y_bin_test, alarme_test_cal, zero_division=0)) if y_bin_test.sum() > 0 else 0.0
        result[f"cal_test_k{k}_f1"] = float(f1_score(y_bin_test, alarme_test_cal, zero_division=0)) if y_bin_test.sum() > 0 else 0.0

        if k == 1:
            # Spearman no TESTE entre max_dia e prob m1
            max_dia_test = test["max_dia"].to_numpy()
            rho_base, p_base = spearmanr(max_dia_test, prob_test_base)
            rho_cal, p_cal = spearmanr(max_dia_test, prob_test_cal)
            result["base_spearman_rho"] = float(rho_base)
            result["base_spearman_p"] = float(p_base)
            result["cal_spearman_rho"] = float(rho_cal)
            result["cal_spearman_p"] = float(p_cal)

    return result


def main():
    print("Building dataset with leak-corrected api_* ...")
    df_ml, estacoes_bacia, p50 = build_dataset()

    if "enchente" not in df_ml.columns:
        df_ml = df_ml.with_columns((pl.col("severidade") >= 1).alias("enchente"))

    todos = []
    for bacia in sorted(estacoes_bacia.keys()):
        sub = df_ml.filter(pl.col("bacia") == bacia).drop_nulls(FEATURES)
        r = train_and_eval(bacia, sub)
        if r is None:
            print(f"  {bacia}: pulado (dados insuficientes)")
            continue
        todos.append(r)

        print(f"\n{'='*80}")
        print(f"  {bacia.upper()} (train_n={r['train_n']}, val_n={r['val_n']}, test_n={r['test_n']})")
        print(f"  Severidade train: {r['sev_dist_train']}")
        print(f"  Severidade test:  {r['sev_dist_test']}")
        print(f"\n  {'k':>2}  {'Versão':>10}  {'Thr':>6}  {'PRAUC':>6}  {'Recall':>7}  {'Prec':>6}  {'F1':>5}")
        for k in [1, 2, 3]:
            for prefix, label in [("base", "baseline"), ("cal", "isotonic")]:
                print(f"  {k:>2}  {label:>10}  "
                      f"{r[f'{prefix}_test_k{k}_thr']:>6.3f}  "
                      f"{r[f'{prefix}_test_k{k}_prauc']:>6.3f}  "
                      f"{r[f'{prefix}_test_k{k}_recall']:>7.3f}  "
                      f"{r[f'{prefix}_test_k{k}_prec']:>6.3f}  "
                      f"{r[f'{prefix}_test_k{k}_f1']:>5.3f}")
        print(f"\n  Spearman ρ (max_dia vs prob m1) — test set:")
        print(f"    baseline: {r['base_spearman_rho']:.3f} (p={r['base_spearman_p']:.3g})")
        print(f"    isotonic: {r['cal_spearman_rho']:.3f} (p={r['cal_spearman_p']:.3g})")

    import pandas as pd
    df_res = pd.DataFrame(todos)
    for col in ["sev_dist_train", "sev_dist_test"]:
        df_res[col] = df_res[col].apply(lambda d: str({str(k): v for k, v in d.items()}))
    out_path = OUT_DIR / "calibracao_probabilidade.parquet"
    df_res.to_parquet(out_path)
    print(f"\nResultados salvos em {out_path}")


if __name__ == "__main__":
    main()
