"""
Exporta artefatos champion V7 por bacia com leak corrigido nas features api_*.

O leak original usava max_dia[t] (dia atual, incompleto em produção).
Correção: aplica shift(1) em max_dia antes do lfilter, de modo que
api_*[t] depende apenas de max_dia[t-1], t-2, ...

Saídas (por bacia):
  modelos/champion_<bacia>.joblib     — objeto ChampionOrdinalModel
  modelos/champion_<bacia>.json       — metadados (thresholds, features, etc.)
"""

import json
import sys
import warnings
from datetime import datetime, date, timezone
from functools import reduce
from pathlib import Path

import joblib
import numpy as np
import polars as pl
from scipy.signal import lfilter
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import precision_recall_curve
from sklearn.model_selection import TimeSeriesSplit

# Adiciona backend/floodcast ao path para importar ChampionOrdinalModel
_BACKEND_ROOT = Path(__file__).resolve().parents[3] / "backend" / "floodcast"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from floodcast.ordinal_model import ChampionOrdinalModel

MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
JANELAS_H = [1, 3, 6, 24, 48, 72]
LIMS = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
LOOKBACK_H = 72
T_CUT = datetime(2023, 7, 2).date()
K_APIS = [0.70, 0.85, 0.95]
LIM_INTENSO_MM = 5.0

FEATURES_V4 = (
    [f"api_{int(k*100):03d}" for k in K_APIS]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]
)

MODELING_FAMILY = "psa_v7_ordinal"
OBJ_VERSION = "0.3"


def _mk_classifier(_sw: float = 0.0) -> GradientBoostingClassifier:
    """Factory do GradBoost champion."""
    return GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05,
        max_depth=2, min_samples_leaf=10,
        subsample=0.8, max_features="sqrt",
        random_state=42,
    )


def _fit_with_sw(clf, X, y, sw_arr):
    if hasattr(clf, "fit"):
        clf.fit(X, y, sample_weight=sw_arr)
    return clf


def _thr_por_f1(y_true, y_prob):
    prec, rec, thrs = precision_recall_curve(y_true, y_prob)
    if len(thrs) == 0:
        return 0.5
    f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
    return float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5


def thr_por_f1_cv(mk, X, y_bin, sw_arr, n_splits=5):
    tscv = TimeSeriesSplit(n_splits=n_splits)
    oof = np.full(len(y_bin), np.nan)
    for tr_idx, va_idx in tscv.split(X):
        if y_bin[tr_idx].sum() == 0 or y_bin[va_idx].sum() == 0:
            continue
        clf = mk(0.0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _fit_with_sw(clf, X.iloc[tr_idx], y_bin[tr_idx], sw_arr[tr_idx])
        oof[va_idx] = clf.predict_proba(X.iloc[va_idx])[:, 1]
    mask = ~np.isnan(oof)
    if mask.sum() == 0 or y_bin[mask].sum() == 0:
        return 0.5
    return _thr_por_f1(y_bin[mask], oof[mask])


def w_fit_m3(severidade):
    return np.where(
        severidade == 3, 3.0,
        np.where(severidade == 2, 1.5,
        np.where(severidade == 1, 1.0, 1.0))
    )


def build_features():
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
                pl.concat_list(est_cols).list.std().alias("chuva_std_mm"),
                pl.sum_horizontal([(pl.col(c) > 1.0).cast(pl.Int8) for c in est_cols]).alias("n_chovendo"),
            ])
            .select(["hora", "chuva_max_mm", "chuva_mean_mm", "chuva_std_mm", "n_chovendo"])
            .with_columns(pl.lit(bacia).alias("bacia"))
        )
    df_chuva_h = pl.concat(partes).sort(["bacia", "hora"])

    df_chamados_raw = pl.read_parquet("dados/chamados_por_bacia.parquet")
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

    df_h = (
        df_chuva_h
        .with_columns([
            pl.col("hora").dt.date().alias("data"),
            (pl.col("hora").dt.hour() // 6).alias("bloco_6h"),
        ])
    )
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
        .with_columns([pl.col(c).fill_null(0) for c in ["bloco_0", "bloco_1", "bloco_2", "bloco_3"]])
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
        .select(
            ["data", "bacia"]
            + [f"acc_6h_lag_{i}" for i in range(1, 13)]
            + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
            + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
            + ["pico_1h_lag1", "horas_intensas_lag1"]
            + ["acum_7d", "acum_30d"]
            + ["mes_sin", "mes_cos"]
        )
    )

    # CORREÇÃO DO LEAK: shift(1) em max_dia antes do lfilter
    # para que api_*[t] dependa apenas de max_dia[t-1], t-2, ...
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

    # target ordinal
    _chamados_diario = (
        df_chamados_conf
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .group_by(["data", "bacia"]).len().rename({"len": "n_chamados"})
    )

    _ext = pl.read_csv("dados/alagamentos_bacias.csv").with_columns(pl.col("dt").str.to_date())
    _df_ext = _ext.select([
        pl.col("dt").alias("data"),
        pl.col("bacia_tamanduatei").alias("tamanduatei"),
        pl.col("bacia_guarara").alias("guarara"),
        pl.col("bacia_oratorio").alias("oratorio"),
        pl.col("bacia_meninos").alias("meninos"),
    ]).unpivot(index="data", variable_name="bacia", value_name="flag").filter(pl.col("flag") > 0).select([
        "data", "bacia", pl.lit(True).alias("pos_externo"),
    ])

    _bacias = list(estacoes_bacia.keys())
    _datas = pl.date_range(date(2016, 1, 1), date(2025, 12, 31), interval="1d", eager=True).to_list()
    _cal = pl.DataFrame({
        "data": pl.Series([d for d in _datas for _ in _bacias], dtype=pl.Date),
        "bacia": [b for _ in _datas for b in _bacias],
    })

    _max_dia = df_diario.select(["data", "bacia", "max_dia"])
    _chamados_max = _chamados_diario.join(_max_dia, on=["data", "bacia"], how="left").filter(pl.col("data") < T_CUT)
    P50_BY_BACIA = {}
    for _b in _bacias:
        _s = _chamados_max.filter(pl.col("bacia") == _b)
        if _s.height > 0:
            P50_BY_BACIA[_b] = float(_s["max_dia"].quantile(0.5))
        else:
            P50_BY_BACIA[_b] = float(_max_dia.filter(pl.col("bacia") == _b)["max_dia"].quantile(0.95))

    df_ml = (
        _cal
        .join(_chamados_diario, on=["data", "bacia"], how="left")
        .join(_df_ext, on=["data", "bacia"], how="left")
        .join(_max_dia, on=["data", "bacia"], how="left")
        .with_columns([
            pl.col("n_chamados").fill_null(0),
            pl.col("pos_externo").fill_null(False),
        ])
    )
    _p50_expr = pl.col("bacia").replace_strict(P50_BY_BACIA, return_dtype=pl.Float64)
    df_ml = df_ml.with_columns(
        pl.when((pl.col("n_chamados") >= 5) | pl.col("pos_externo")).then(3)
        .when(pl.col("n_chamados").is_between(2, 4)).then(2)
        .when((pl.col("n_chamados") == 1) | ((pl.col("n_chamados") == 0) & (pl.col("max_dia") > _p50_expr))).then(1)
        .otherwise(0)
        .alias("severidade")
    )
    df_ml = df_ml.join(df_feat, on=["data", "bacia"], how="left").filter(
        pl.col("data").dt.month().is_in(MESES_CHUVOSOS)
    ).sort(["bacia", "data"])

    return df_ml, estacoes_bacia, P50_BY_BACIA


def export_bacia(bacia, df_ml, out_dir: Path):
    sub = df_ml.filter(pl.col("bacia") == bacia).drop_nulls(FEATURES_V4)
    X = sub[FEATURES_V4].to_pandas()
    sev = sub["severidade"].to_numpy()

    pipelines = {}
    thresholds = {}
    for k in [1, 2, 3]:
        y_bin = (sev >= k).astype(int)
        if y_bin.sum() < 2:
            # modelo impossível de treinar — threshold que nunca dispara
            pipelines[k] = None
            thresholds[k] = 1.5
            continue
        if k == 3:
            sw_arr = w_fit_m3(sev).astype(float)
        else:
            sw_arr = np.ones(len(sev), dtype=float)
        thr = thr_por_f1_cv(_mk_classifier, X, y_bin, sw_arr, n_splits=5)
        clf = _mk_classifier(0.0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _fit_with_sw(clf, X, y_bin, sw_arr)
        pipelines[k] = clf
        thresholds[k] = thr

    model = ChampionOrdinalModel(
        pipelines=pipelines,
        thresholds=thresholds,
        features=FEATURES_V4,
        bacia=bacia,
        modeling_family=MODELING_FAMILY,
        obj_version=OBJ_VERSION,
        metadata={
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "n_samples": int(len(X)),
            "class_distribution": {int(s): int((sev == s).sum()) for s in [0, 1, 2, 3]},
        },
    )

    joblib_path = out_dir / f"champion_{bacia}.joblib"
    json_path = out_dir / f"champion_{bacia}.json"

    joblib.dump(model, joblib_path)

    meta = {
        "bacia": bacia,
        "modeling_family": MODELING_FAMILY,
        "obj_version": OBJ_VERSION,
        "features": FEATURES_V4,
        "thresholds": {str(k): float(v) for k, v in thresholds.items()},
        "n_samples": int(len(X)),
        "class_distribution": {int(s): int((sev == s).sum()) for s in [0, 1, 2, 3]},
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(json_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"  {bacia}: exported -> {joblib_path.name} ({len(X)} samples)")
    return model


def main():
    out_dir = Path("modelos")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Building features with leak-corrected api_* ...")
    df_ml, estacoes_bacia, _ = build_features()

    print("\nExporting champions per bacia ...")
    for bacia in sorted(estacoes_bacia.keys()):
        export_bacia(bacia, df_ml, out_dir)

    print(f"\nAll champions exported to {out_dir}/")


if __name__ == "__main__":
    main()
