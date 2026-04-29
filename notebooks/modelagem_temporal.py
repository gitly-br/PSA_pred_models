import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    import json
    import marimo as mo
    import altair as alt
    import numpy as np
    from datetime import date
    from functools import reduce
    return alt, date, json, mo, np, pl, reduce


@app.cell
def _():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import (
        average_precision_score, f1_score, precision_recall_curve,
        precision_score, recall_score,
    )
    return (
        RandomForestClassifier,
        average_precision_score,
        f1_score,
        precision_recall_curve,
        precision_score,
        recall_score,
    )


@app.cell
def _():
    HORIZONTES_H  = [3, 6, 12, 24, 48]
    MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
    LOOKBACK_H    = 72
    LIMS = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
    JANELAS_H     = [1, 3, 6, 24, 48, 72]
    TEST_SIZE     = 0.25
    FEATURES = [
        "rolling_1h", "rolling_3h", "rolling_6h", "rolling_12h",
        "rolling_24h", "rolling_48h", "rolling_72h",
        "peak_1h_3h", "peak_1h_6h", "peak_1h_12h",
        "horas_consecutivas_chuva", "dias_desde_ultima_chuva",
    ]
    return FEATURES, HORIZONTES_H, JANELAS_H, LIMS, LOOKBACK_H, MESES_CHUVOSOS, TEST_SIZE


@app.cell
def _(mo):
    mo.md(
        r"""
        # Modelagem Temporal — Previsão de Enchentes por Horizonte

        Abordagem multi-horizonte: para cada hora H e bacia B, prevemos se haverá
        enchente nas próximas N horas (N ∈ {3, 6, 12, 24, 48}).

        Um modelo Random Forest por (bacia, horizonte) — 4 × 5 = 20 modelos no total.

        **Diferenças em relação ao baseline diário:**
        - Resolução horária: ~175k amostras por bacia nos meses chuvosos (vs ~1.800 dias)
        - Target `dt_ajustado`: hora do pico de chuva que precedeu o chamado, não a hora da ligação
        - Features calculadas hora a hora, olhando para trás a partir de H
        - Avaliação por horizonte revela em quantas horas de antecedência o modelo consegue detectar
        """
    )
    return


@app.cell
def _(mo):
    mo.md(r"## 1. Carga de dados")
    return


@app.cell
def _(json, pl):
    with open("dados/estacoes_bacia.json") as _f:
        estacoes_bacia = json.load(_f)

    _partes = []
    for _bacia in estacoes_bacia:
        _df = pl.read_parquet(f"dados/chuva_bacias/chuva_{_bacia}.parquet")
        _est_cols = [c for c in _df.columns if c != "hora"]
        _partes.append(
            _df
            .with_columns([
                pl.max_horizontal(_est_cols).alias("chuva_max_mm"),
                pl.mean_horizontal(_est_cols).alias("chuva_mean_mm"),
            ])
            .select(["hora", "chuva_max_mm"])
            .with_columns(pl.lit(_bacia).alias("bacia"))
        )

    df_chuva_h = pl.concat(_partes).sort(["bacia", "hora"])
    return df_chuva_h, estacoes_bacia


@app.cell
def _(pl):
    df_chamados_raw = pl.read_parquet("dados/chamados_por_bacia.parquet")
    return (df_chamados_raw,)


@app.cell
def _(df_chuva_h, df_chamados_raw, mo, pl):
    _stats = (
        df_chuva_h
        .group_by("bacia")
        .agg([
            pl.len().alias("n_horas"),
            (pl.col("chuva_max_mm") > 0).sum().alias("horas_com_chuva"),
        ])
        .sort("bacia")
    )
    mo.vstack([
        mo.callout(mo.md(
            f"**{len(df_chuva_h):,}** registros horários · "
            f"**{df_chamados_raw.height:,}** chamados carregados"
        ), kind="success"),
        mo.ui.table(_stats),
    ])
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## 2. `dt_ajustado` — hora do pico de chuva por chamado

        Para cada chamado, buscamos nas 72h anteriores a hora com maior acumulado
        de 1h na série da bacia. Essa hora (`dt_ajustado`) ancora o evento de enchente
        no tempo com mais precisão do que o horário da ligação (`dt_abertura`), que pode
        ser horas após o início do alagamento.

        Chamados sem confirmação de chuva na bacia (`confirmado_chuva_bacia = False`)
        são descartados — não têm âncora temporal confiável.
        """
    )
    return


@app.cell
def _(JANELAS_H, LIMS, LOOKBACK_H, df_chamados_raw, df_chuva_h, pl, reduce):
    _chamados_idx = (
        df_chamados_raw
        .drop_nulls("dt_abertura")
        .filter(pl.col("bacia").is_not_null())
        .with_row_index("_idx")
        .with_columns([
            (pl.col("dt_abertura") - pl.duration(hours=LOOKBACK_H)).alias("dt_inicio"),
            pl.col("dt_abertura").alias("dt_fim"),
        ])
        .rename({"bacia": "bacia_cham"})
    )

    _joined = (
        _chamados_idx
        .join_where(
            df_chuva_h,
            pl.col("hora") >= pl.col("dt_inicio"),
            pl.col("hora") <= pl.col("dt_fim"),
        )
        .filter(pl.col("bacia_cham") == pl.col("bacia"))
        .select(["_idx", "hora", "chuva_max_mm"])
        .sort(["_idx", "hora"])
    )

    # confirmado_chuva_bacia — igual ao baseline
    _accs = _chamados_idx.select("_idx")
    for _h in JANELAS_H:
        _sub = (
            _joined
            .rolling("hora", period=f"{_h}h", group_by="_idx")
            .agg(pl.col("chuva_max_mm").sum().alias("acc"))
            .group_by("_idx")
            .agg(pl.col("acc").max().alias(f"acc_{_h}h"))
        )
        _accs = _accs.join(_sub, on="_idx", how="left")

    _cond = reduce(
        lambda a, b: a | b,
        [pl.col(f"acc_{h}h").fill_null(0) >= LIMS[h] for h in JANELAS_H],
    )

    # dt_ajustado = hora do pico de acumulado 1h dentro da janela de 72h
    _peak = (
        _joined
        .rolling("hora", period="1h", group_by="_idx")
        .agg(pl.col("chuva_max_mm").sum().alias("acc_1h"))
        .group_by("_idx")
        .agg(
            pl.col("hora").sort_by("acc_1h", descending=True).first().alias("dt_ajustado")
        )
    )

    df_chamados_conf = (
        df_chamados_raw
        .drop_nulls("dt_abertura")
        .filter(pl.col("bacia").is_not_null())
        .with_row_index("_idx")
        .join(_accs, on="_idx", how="left")
        .join(_peak, on="_idx", how="left")
        .drop("_idx")
        .with_columns([
            _cond.alias("confirmado_chuva_bacia"),
            pl.coalesce(["dt_ajustado", "dt_abertura"]).alias("dt_ajustado"),
        ])
        .filter(pl.col("confirmado_chuva_bacia"))
        .select(["dt_abertura", "dt_ajustado", "bacia"])
    )
    return (df_chamados_conf,)


@app.cell
def _(df_chamados_conf, mo, pl):
    _desvio = (
        df_chamados_conf
        .with_columns(
            ((pl.col("dt_ajustado") - pl.col("dt_abertura")).dt.total_seconds() / 3600)
            .abs()
            .alias("desvio_h")
        )
    )
    _por_bacia = (
        _desvio
        .group_by("bacia")
        .agg([
            pl.len().alias("chamados_confirmados"),
            pl.col("desvio_h").mean().round(1).alias("desvio_medio_h"),
            pl.col("desvio_h").max().round(1).alias("desvio_max_h"),
            (pl.col("desvio_h") == 0).sum().alias("sem_desvio"),
        ])
        .sort("bacia")
    )
    mo.vstack([
        mo.md("**Chamados confirmados com `dt_ajustado`**"),
        mo.ui.table(_por_bacia),
        mo.md(
            r"""
            `desvio_medio_h` = diferença média entre `dt_ajustado` (pico de chuva) e
            `dt_abertura` (hora da ligação). Valores altos indicam que as pessoas ligam
            horas após o pico — esperado para enchentes que persistem.
            `sem_desvio` = chamados onde o pico coincide com a ligação (dt_abertura já era o pico).
            """
        ),
    ])
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## 3. Feature engineering horária

        Para cada hora H da série, calculamos features olhando para trás:
        acumulados rolling (1h–72h), pico de intensidade em janelas curtas,
        persistência da chuva e tempo desde o último evento.

        Features calculadas na série completa e depois filtradas para os meses
        chuvosos (nov–abr), evitando janelas incompletas nas bordas da estação.
        """
    )
    return


@app.cell
def _(df_chuva_h, pl):
    # threshold global: p5 dos valores positivos de chuva_max_mm
    _vals_positivos = df_chuva_h.filter(pl.col("chuva_max_mm") > 0)["chuva_max_mm"]
    LIMIAR_CHUVA = float(_vals_positivos.quantile(0.05))
    LIMIAR_CHUVA
    return (LIMIAR_CHUVA,)


@app.cell
def _(LIMIAR_CHUVA, MESES_CHUVOSOS, df_chuva_h, pl):
    df_features = (
        df_chuva_h
        .sort(["bacia", "hora"])
        # acumulados rolling
        .with_columns([
            pl.col("chuva_max_mm").rolling_sum(window_size=w, min_samples=1)
              .over("bacia").alias(f"rolling_{w}h")
            for w in [1, 3, 6, 12, 24, 48, 72]
        ])
        # pico de intensidade 1h dentro de janelas curtas
        .with_columns([
            pl.col("chuva_max_mm").rolling_max(window_size=w, min_samples=1)
              .over("bacia").alias(f"peak_1h_{w}h")
            for w in [3, 6, 12]
        ])
        # flag tem_chuva e grupo para horas_consecutivas
        .with_columns(
            (pl.col("chuva_max_mm") > LIMIAR_CHUVA).alias("_tem_chuva")
        )
        .with_columns(
            (~pl.col("_tem_chuva")).cast(pl.Int32).cum_sum()
              .over("bacia").alias("_grupo_seco")
        )
        .with_columns(
            pl.when(pl.col("_tem_chuva"))
              .then(
                  pl.col("_tem_chuva").cast(pl.Int32).cum_sum()
                    .over(["bacia", "_grupo_seco"])
              )
              .otherwise(0)
              .alias("horas_consecutivas_chuva")
        )
        # dias desde última chuva
        .with_columns(
            pl.when(pl.col("_tem_chuva"))
              .then(pl.col("hora"))
              .otherwise(None)
              .forward_fill()
              .over("bacia")
              .alias("_ultima_chuva")
        )
        .with_columns(
            ((pl.col("hora") - pl.col("_ultima_chuva")).dt.total_hours() / 24.0)
              .alias("dias_desde_ultima_chuva")
        )
        .drop(["_tem_chuva", "_grupo_seco", "_ultima_chuva"])
        # filtra meses chuvosos após calcular features
        .filter(pl.col("hora").dt.month().is_in(MESES_CHUVOSOS))
    )
    df_features.shape
    return (df_features,)


@app.cell
def _(FEATURES, df_features, mo, pl):
    _nulls = (
        df_features
        .select([pl.col(f).null_count().alias(f) for f in FEATURES])
        .unpivot(variable_name="feature", value_name="nulls")
        .sort("feature")
    )
    _stats = (
        df_features
        .select(FEATURES)
        .describe()
    )
    mo.vstack([
        mo.callout(
            mo.md(
                f"**{df_features.shape[0]:,}** horas × **{len(FEATURES)}** features "
                f"· meses chuvosos · {df_features['bacia'].n_unique()} bacias"
            ),
            kind="success",
        ),
        mo.md("**Nulls por feature:**"),
        mo.ui.table(_nulls),
        mo.md("**Estatísticas descritivas:**"),
        mo.ui.table(_stats),
    ])
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## 4. Targets multi-horizonte

        Para cada hora H e bacia, o target binário responde:
        *"haverá uma ligação de enchente nas próximas N horas?"*

        `target_N[H] = 1` se existir algum `dt_abertura` (truncado à hora) no intervalo `(H, H+N]`.

        Usar `dt_abertura` (hora da ligação) em vez de `dt_ajustado` (pico de chuva) é
        mais natural: a chuva acumulada até H prediz se o alagamento já em curso vai
        gerar chamados nas próximas horas.

        Rolling forward implementado revertendo a série, aplicando `rolling_sum(N+1)`
        e subtraindo o valor na hora H (que não pertence ao futuro).
        """
    )
    return


@app.cell
def _(HORIZONTES_H, MESES_CHUVOSOS, df_chamados_conf, df_features, pl):
    # eventos: dt_abertura truncado à hora (hora da ligação, não do pico de chuva)
    _eventos = (
        df_chamados_conf
        .filter(pl.col("dt_abertura").dt.month().is_in(MESES_CHUVOSOS))
        .with_columns(
            pl.col("dt_abertura").dt.truncate("1h").dt.cast_time_unit("us").alias("hora_trunc")
        )
        .group_by(["bacia", "hora_trunc"])
        .len()
        .rename({"hora_trunc": "hora", "len": "n_eventos"})
    )

    df_targets = (
        df_features
        .select(["bacia", "hora"] + [f for f in df_features.columns if f not in ["bacia", "hora", "chuva_max_mm"]])
        .join(_eventos, on=["bacia", "hora"], how="left")
        .with_columns(pl.col("n_eventos").fill_null(0).cast(pl.Int32))
        .sort(["bacia", "hora"])
        .with_columns([
            (
                pl.col("n_eventos").reverse()
                  .rolling_sum(window_size=N + 1, min_samples=1)
                  .reverse()
                  .over("bacia")
                - pl.col("n_eventos")
            ).gt(0).cast(pl.Int8).alias(f"target_{N}h")
            for N in HORIZONTES_H
        ])
    )
    df_targets.shape
    return (df_targets,)


@app.cell
def _(HORIZONTES_H, df_targets, mo, pl):
    _rows = []
    for _bacia in sorted(df_targets["bacia"].unique().to_list()):
        _sub = df_targets.filter(pl.col("bacia") == _bacia)
        for _N in HORIZONTES_H:
            _pos = _sub[f"target_{_N}h"].sum()
            _total = _sub.height
            _rows.append({
                "bacia": _bacia,
                "horizonte": f"{_N}h",
                "positivos": int(_pos),
                "total": _total,
                "% positivos": round(100 * _pos / _total, 2),
            })

    _df_bal = pl.DataFrame(_rows)
    mo.vstack([
        mo.md("**Balanceamento de classes por bacia e horizonte**"),
        mo.ui.table(_df_bal),
        mo.callout(
            mo.md("Desbalanceamento esperado — modelos serão treinados com `class_weight='balanced'`."),
            kind="info",
        ),
    ])
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## 5. Treino e avaliação — 20 modelos (4 bacias × 5 horizontes)

        Split temporal por bacia (75% treino / 25% test):
        - guarara, meninos, tamanduatei: corte em 2023-07-02
        - oratorio: corte no 75º percentil de `dt_abertura` (≈jan/2023) — sem ligações registradas após essa data

        Threshold ótimo por (bacia, horizonte): maximiza F1 na curva PR do test.
        RandomForest 200 árvores, `class_weight='balanced'`.
        """
    )
    return


@app.cell
def _(df_chamados_conf, pl):
    from datetime import datetime

    _T_CUT_GLOBAL = datetime(2023, 7, 2)

    _eventos_oratorio = (
        df_chamados_conf
        .filter(pl.col("bacia") == "oratorio")
        ["dt_abertura"].dt.truncate("1h").unique().sort()
    )
    _t_cut_oratorio = _eventos_oratorio[int(len(_eventos_oratorio) * 0.75)]

    cortes_split = {
        "guarara":     _T_CUT_GLOBAL,
        "meninos":     _T_CUT_GLOBAL,
        "oratorio":    _t_cut_oratorio.replace(tzinfo=None),
        "tamanduatei": _T_CUT_GLOBAL,
    }
    cortes_split
    return (cortes_split,)


@app.cell
def _(
    FEATURES, HORIZONTES_H, RandomForestClassifier, average_precision_score,
    cortes_split, df_targets, f1_score, np, pl, precision_recall_curve,
    precision_score, recall_score,
):
    import warnings

    _resultados = []

    for _bacia in sorted(df_targets["bacia"].unique().to_list()):
        _t_cut = cortes_split[_bacia]
        _sub = df_targets.filter(pl.col("bacia") == _bacia).drop_nulls(FEATURES)

        _train = _sub.filter(pl.col("hora") < _t_cut)
        _test  = _sub.filter(pl.col("hora") >= _t_cut)

        _X_train = _train[FEATURES].to_numpy()
        _X_test  = _test[FEATURES].to_numpy()

        for _N in HORIZONTES_H:
            _col = f"target_{_N}h"
            _y_train = _train[_col].to_numpy()
            _y_test  = _test[_col].to_numpy()

            if _y_test.sum() == 0:
                continue

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _rf = RandomForestClassifier(
                    n_estimators=200,
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=-1,
                )
                _rf.fit(_X_train, _y_train)

            _y_prob = _rf.predict_proba(_X_test)[:, 1]

            _prec, _rec, _thresholds = precision_recall_curve(_y_test, _y_prob)
            _f1s = 2 * _prec[:-1] * _rec[:-1] / (_prec[:-1] + _rec[:-1] + 1e-9)
            _best_thr = float(_thresholds[np.argmax(_f1s)])
            _y_pred = (_y_prob >= _best_thr).astype(int)

            _resultados.append({
                "bacia":      _bacia,
                "horizonte":  f"{_N}h",
                "threshold":  round(_best_thr, 3),
                "f1":         round(float(f1_score(_y_test, _y_pred)), 3),
                "recall":     round(float(recall_score(_y_test, _y_pred)), 3),
                "precisao":   round(float(precision_score(_y_test, _y_pred)), 3),
                "pr_auc":     round(float(average_precision_score(_y_test, _y_prob)), 3),
                "test_pos":   int(_y_test.sum()),
                "test_total": int(len(_y_test)),
            })

    df_metricas = pl.DataFrame(_resultados)
    df_metricas
    return (df_metricas,)


@app.cell
def _(df_metricas, mo):
    mo.vstack([
        mo.md("**Métricas por bacia e horizonte** — threshold otimizado por F1"),
        mo.ui.table(df_metricas),
        mo.callout(
            mo.md(
                "oratorio: test = jan–abr/2023 (última temporada com eventos registrados). "
                "Demais bacias: test = jul/2023–dez/2025."
            ),
            kind="info",
        ),
    ])
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## 6. Comparação com o baseline diário

        O baseline (`modelagem_baseline.py`) opera em resolução diária: uma amostra por (dia, bacia),
        target = "houve enchente neste dia?". O modelo temporal no horizonte 24h é o mais comparável.

        Ambos re-treinados com **split temporal idêntico** (corte 2023-07-02) e **threshold otimizado
        por F1**, para comparação justa.

        | Bacia | Baseline PR-AUC | Temporal 24h PR-AUC |
        |---|---|---|
        | guarara | 0.187 | 0.040 |
        | meninos | 0.224 | 0.032 |
        | oratorio | 0.157 | 0.091 |
        | tamanduatei | 0.258 | 0.056 |

        **O baseline diário vence em todas as bacias.** A granularidade horária não ajuda para 24h:
        a agregação diária filtra ruído intradiário e o target (dia com enchente) é mais estável.

        Há também um viés na avaliação do modelo temporal: cada evento de enchente cria ~24 horas
        positivas correlacionadas no test set (vs. 1 dia independente no baseline), tornando a
        avaliação mais ruidosa.

        **O valor dos modelos temporais está nos horizontes curtos (3h, 6h)**, que o baseline
        diário não consegue responder. Para esses horizontes, o modelo temporal tem PR-AUC
        3–10x acima do aleatório e pode funcionar como apoio à decisão.

        ### Leitura operacional

        Com precisão de 0.1–0.3 e recall de 0.3–0.6, os modelos atuais não têm qualidade para
        automação. O caso de uso mais realista é **apoio à decisão**: o modelo levanta um alerta,
        um operador decide se aciona equipes.

        Para automação completa seria necessário: forecast de chuva, dados de nível de rios,
        ou índice de saturação do solo.
        """
    )
    return


if __name__ == "__main__":
    app.run()
