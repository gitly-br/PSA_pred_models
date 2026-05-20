"""
Valida Risk Model V1 robusto contra chamados de enchente 2026.

Saidas:
- dados/results/validacao_chamados_2026_risk_v1_scores.parquet
- dados/results/validacao_chamados_2026_risk_v1_station_rain.parquet
- dados/results/relatorio_validacao_chamados_2026_risk_v1.md
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl


WORKDIR = Path(__file__).resolve().parents[2]
OUT_DIR = WORKDIR / "dados" / "results"
VALIDACAO_PATH = WORKDIR / "dados" / "validacao" / "chamados_validacao_2026.parquet"
RISK_SCRIPT = WORKDIR / "scripts" / "experiments" / "_risk_model_v1_station_contract_robust.py"

T_CUT = date(2023, 7, 2)
MODEL_NAME = "gradboost_cons"
VARIANTE = "CEMADEN_OM"
LABELS = ["pancada", "prolongada", "saturante", "perigoso_any"]
SPECIAL_2026_DATES = [date(2026, 4, 1), date(2026, 3, 31), date(2026, 4, 19), date(2026, 4, 10)]


def load_risk_module():
    spec = importlib.util.spec_from_file_location("risk_robust", RISK_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["risk_robust"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_feature_table(risk):
    estacoes_bacia = risk.load_station_contract()
    df_hourly = risk.build_hourly_data(estacoes_bacia)
    df_diario = risk.build_daily_cemaden(df_hourly, estacoes_bacia)
    df_diario, _, _ = risk.build_targets(df_diario, estacoes_bacia, risk.T_CUT)
    df_feat = risk.build_features(df_diario)
    df_om = risk.build_openmeteo_forecast_features()
    df_feat = risk.add_openmeteo_features(df_feat, df_om)

    om_cols = [c for c in df_feat.columns if c.startswith("om_")]
    for c in om_cols:
        if "precip" in c or "rain" in c:
            df_feat = df_feat.with_columns(pl.col(c).fill_null(0))
        else:
            med = df_feat[c].median()
            df_feat = df_feat.with_columns(pl.col(c).fill_null(pl.lit(med) if med is not None else 0))
    df_feat = risk.add_risk_components(df_feat)
    return estacoes_bacia, df_hourly, df_feat


def cemaden_om_columns(df_feat: pl.DataFrame):
    cemaden_vars = (
        [f"api_{int(k*100):03d}" for k in [0.70, 0.85, 0.95]]
        + [
            "max_day_lag1",
            "max_day_lag2",
            "max_day_lag3",
            "acum_dia_lag1",
            "mean_day_lag1",
            "std_day_lag1",
            "n_chovendo_max_lag1",
            "pico_1h_lag1",
            "horas_intensas_lag1",
            "acum_7d",
            "acum_30d",
            "mes_sin",
            "mes_cos",
        ]
    )
    om_vars = []
    for h in [24, 48]:
        om_vars += [
            f"om_precip_sum_h{h}",
            f"om_rain_max_h{h}",
            f"om_temp_mean_h{h}",
            f"om_humidity_mean_h{h}",
            f"om_wind_max_h{h}",
            f"om_pressure_mean_h{h}",
        ]
    return [c for c in cemaden_vars + om_vars if c in df_feat.columns]


def validation_dates(df_feat: pl.DataFrame):
    chamados = pl.read_parquet(VALIDACAO_PATH)
    event_dates = chamados["data_ocorrencia"].unique().sort().to_list()

    # Controles secos fora da estacao chuvosa em 2025: todos os rios/bacias com max_dia <= 0.1.
    dry = (
        df_feat.filter(
            (pl.col("data") >= date(2025, 6, 1))
            & (pl.col("data") <= date(2025, 9, 30))
        )
        .group_by("data")
        .agg(pl.col("max_dia").max().alias("max_all_bacias"))
        .filter(pl.col("max_all_bacias") <= 0.1)
        .sort("data")
        .head(4)["data"]
        .to_list()
    )

    rows = []
    for d in event_dates:
        rows.append({"data": d, "grupo": "chamado_2026"})
    for d in SPECIAL_2026_DATES:
        rows.append({"data": d, "grupo": "checagem_2026_usuario"})
    for d in dry:
        rows.append({"data": d, "grupo": "controle_seco_2025"})
    return pl.DataFrame(rows).unique(["data", "grupo"]), chamados


def score_dates(risk, df_feat: pl.DataFrame, target_dates: pl.DataFrame, chamados: pl.DataFrame):
    cols = cemaden_om_columns(df_feat)
    rows = []
    chamado_counts = (
        chamados.group_by(["data_ocorrencia", "bacia"])
        .len()
        .rename({"data_ocorrencia": "data", "len": "n_chamados_validacao"})
    )

    for bacia in sorted(df_feat["bacia"].unique().to_list()):
        sub_all = df_feat.filter(pl.col("bacia") == bacia).sort("data").drop_nulls(cols + LABELS + ["max_dia"])
        if sub_all.height == 0:
            continue
        for target in target_dates.iter_rows(named=True):
            target_date = target["data"]
            target_row = sub_all.filter(pl.col("data") == target_date)
            if target_row.height == 0:
                rows.append({"data": target_date, "grupo": target["grupo"], "bacia": bacia, "status": "sem_dados"})
                continue

            # Para 2026, simula o uso operacional treinando ate 2025. Para controles 2025,
            # usa treino pre-T_CUT para evitar olhar o proprio periodo de teste.
            if target_date.year == 2026:
                train = sub_all.filter(pl.col("data").dt.year() <= 2025)
                train_policy = "train_ate_2025"
            else:
                train = sub_all.filter(pl.col("data") < T_CUT)
                train_policy = "train_pre_t_cut"
            if train.height < 30:
                rows.append({"data": target_date, "grupo": target["grupo"], "bacia": bacia, "status": "treino_insuficiente"})
                continue

            base = {
                "data": target_date,
                "grupo": target["grupo"],
                "bacia": bacia,
                "status": "ok",
                "modelo": MODEL_NAME,
                "variante": VARIANTE,
                "train_policy": train_policy,
                "max_dia": float(target_row["max_dia"][0]),
                "acum_dia": float(target_row["acum_dia"][0]),
                "acum_7d": float(target_row["acum_7d"][0]),
                "acum_30d": float(target_row["acum_30d"][0]),
            }
            call_count = chamado_counts.filter((pl.col("data") == target_date) & (pl.col("bacia") == bacia))
            base["n_chamados_validacao"] = int(call_count["n_chamados_validacao"][0]) if call_count.height else 0

            x_train = train[cols].to_pandas().to_numpy()
            x_target = target_row[cols].to_pandas().to_numpy()
            for label in LABELS:
                y_train = train[label].to_numpy().astype(int)
                if y_train.sum() < 2:
                    base[f"prob_{label}"] = None
                    base[f"target_{label}"] = int(target_row[label][0])
                    continue
                clf = risk.get_model(MODEL_NAME)
                sw = np.where(y_train == 1, 3.0, 0.7).astype(float)
                clf.fit(x_train, y_train, sample_weight=sw)
                base[f"prob_{label}"] = float(clf.predict_proba(x_target)[:, 1][0])
                base[f"target_{label}"] = int(target_row[label][0])
            rows.append(base)
    return pl.DataFrame(rows)


def station_daily_rain(df_hourly: pl.DataFrame, estacoes_bacia: dict, target_dates: pl.DataFrame):
    dates = set(target_dates["data"].to_list())
    rows = []
    for bacia, stations in estacoes_bacia.items():
        sub = df_hourly.filter(pl.col("bacia") == bacia).with_columns(pl.col("hora").dt.date().alias("data"))
        sub = sub.filter(pl.col("data").is_in(list(dates)))
        for d in sorted(dates):
            sub_d = sub.filter(pl.col("data") == d)
            for st in stations:
                if st not in sub_d.columns or sub_d.height == 0:
                    rows.append({"data": d, "bacia": bacia, "station_id": st, "n_registros": 0, "max_1h_mm": None, "acum_mm": None})
                    continue
                s = sub_d[st].drop_nulls()
                rows.append(
                    {
                        "data": d,
                        "bacia": bacia,
                        "station_id": st,
                        "n_registros": int(s.len()),
                        "max_1h_mm": float(s.max()) if s.len() else None,
                        "acum_mm": float(s.sum()) if s.len() else None,
                    }
                )
    return pl.DataFrame(rows)


def write_report(scores: pl.DataFrame, station_rain: pl.DataFrame, chamados: pl.DataFrame):
    report = OUT_DIR / "relatorio_validacao_chamados_2026_risk_v1.md"
    ok = scores.filter(pl.col("status") == "ok")
    event_summary = (
        ok.filter(pl.col("grupo") == "chamado_2026")
        .sort(["data", "bacia"])
        .select(["data", "bacia", "n_chamados_validacao", "max_dia", "prob_perigoso_any", "prob_saturante", "prob_prolongada", "prob_pancada"])
    )
    controls = (
        ok.filter(pl.col("grupo").str.contains("controle|checagem"))
        .sort(["data", "bacia", "grupo"])
        .select(["data", "grupo", "bacia", "max_dia", "prob_perigoso_any", "prob_saturante", "prob_prolongada", "prob_pancada"])
    )
    unavailable = scores.filter(pl.col("status") != "ok")

    def to_md(df: pl.DataFrame, floatfmt: str | None = None) -> str:
        if df.height == 0:
            return "_Sem registros._"
        rows = df.to_dicts()
        cols = df.columns
        out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
        for row in rows:
            vals = []
            for col in cols:
                val = row.get(col)
                if isinstance(val, float) and floatfmt is not None:
                    vals.append(format(val, floatfmt))
                else:
                    vals.append("" if val is None else str(val))
            out.append("| " + " | ".join(vals) + " |")
        return "\n".join(out)

    with report.open("w") as f:
        f.write("# Validação Chamados 2026 — Risk Model V1 Robust\n\n")
        f.write(f"- Modelo: `{MODEL_NAME}`\n")
        f.write(f"- Variante: `{VARIANTE}`\n")
        f.write("- Score principal recomendado: `prob_perigoso_any`\n")
        f.write("- Componentes: `prob_pancada`, `prob_prolongada`, `prob_saturante`\n")
        f.write("- 2026 é pontuado com treino até 2025; controles 2025 usam treino pré-T_CUT.\n\n")
        f.write("## Datas de chamados no arquivo\n\n")
        f.write(to_md(chamados.group_by(["data_ocorrencia", "bacia"]).len().sort(["data_ocorrencia", "bacia"])))
        f.write("\n\n## Probabilidades por bacia nos dias de chamado\n\n")
        f.write(to_md(event_summary, ".3f"))
        f.write("\n\n## Controles e datas solicitadas\n\n")
        f.write(to_md(controls, ".3f"))
        if unavailable.height:
            f.write("\n\n## Datas sem dados para pontuação\n\n")
            f.write(to_md(unavailable.sort(["data", "bacia"])))
        f.write("\n\n## Observação sobre estação vs bacia\n\n")
        f.write(
            "O modelo produz probabilidade por bacia/contrato de estações, não uma probabilidade independente por estação. "
            "O arquivo `validacao_chamados_2026_risk_v1_station_rain.parquet` traz a chuva observada por estação para explicar cada score.\n"
        )
    return report


def main():
    risk = load_risk_module()
    estacoes_bacia, df_hourly, df_feat = build_feature_table(risk)
    target_dates, chamados = validation_dates(df_feat)
    scores = score_dates(risk, df_feat, target_dates, chamados)
    station_rain = station_daily_rain(df_hourly, estacoes_bacia, target_dates)

    scores_path = OUT_DIR / "validacao_chamados_2026_risk_v1_scores.parquet"
    station_path = OUT_DIR / "validacao_chamados_2026_risk_v1_station_rain.parquet"
    scores.write_parquet(scores_path)
    station_rain.write_parquet(station_path)
    report = write_report(scores, station_rain, chamados)

    print(scores_path)
    print(station_path)
    print(report)


if __name__ == "__main__":
    main()
