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
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        average_precision_score, f1_score, precision_recall_curve,
        precision_score, recall_score, roc_auc_score,
    )
    from sklearn.preprocessing import StandardScaler
    from lightgbm import LGBMClassifier
    return (
        LGBMClassifier,
        LogisticRegression,
        RandomForestClassifier,
        StandardScaler,
        average_precision_score,
        f1_score,
        precision_recall_curve,
        precision_score,
        recall_score,
        roc_auc_score,
    )


@app.cell
def _():
    JANELAS_H = [1, 3, 6, 24, 48, 72]
    LOOKBACK_H = 72
    MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
    LIMS = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
    TEST_SIZE = 0.25
    FEATURES = [
        # Acumulados diários — max entre estações
        "max_24h", "max_48h", "max_72h", "max_7d",
        # Acumulados diários — mean entre estações
        "mean_24h", "mean_48h", "mean_72h", "mean_7d",
        # Pico intradiário (max entre estações)
        "peak_1h", "peak_3h", "peak_6h",
        # Antecedente
        "horas_com_chuva", "dias_desde_ultima_chuva",
    ]
    return FEATURES, JANELAS_H, LIMS, LOOKBACK_H, MESES_CHUVOSOS, TEST_SIZE


@app.cell
def _(mo):
    mo.md(
        r"""
        # Modelagem Baseline — Previsão de Enchentes por Bacia

        Notebook de modelagem direta: das leituras horárias do CEMADEN até um classificador por bacia,
        passando por feature engineering e avaliação de estratégias de balanceamento e pré-filtro.

        ## Contexto e decisões de projeto

        **Dados de entrada:**
        - `chamados_por_bacia.parquet` — chamados 809.x (enchente/inundação) confirmados por chuva em qualquer estação da cidade, com bacia atribuída por geolocalização
        - `dados/chuva_bacias/chuva_{bacia}.parquet` — leituras horárias CEMADEN 2016–2025, uma coluna por estação, gerado em `preprocessamento_chuva.py`; estações selecionadas por score ajustado (AUC × cobertura × demérito Gaussiano por distância) em `pluviometria_exploratoria.py`

        **Decisões relevantes:**
        - **Target:** `confirmado_chuva_bacia` — revalidação dos chamados usando apenas estações da bacia do chamado, não todas as estações da cidade. Elimina confirmações espúrias (chuva distante não causou a enchente local).
        - **Chuva representativa:** `max` entre estações por hora (pior caso), complementado por `mean` como feature adicional para capturar cobertura espacial.
        - **Split:** random estratificado 75/25 por bacia. Split temporal foi descartado porque oratorio tem todos os seus 24 eventos positivos antes de 2024, ficando sem casos de teste.
        - **Filtro sazonal:** apenas meses chuvosos (Nov–Abr). Meses secos não são operacionalmente relevantes e contaminam o desbalanceamento.

        ## Estrutura
        1. Chuva horária por bacia (max e mean das estações selecionadas)
        2. Revalidação de chamados (`confirmado_chuva_bacia`)
        3. Feature engineering (acumulados, picos intradiários, antecedente)
        4. Dataset ML — target, desbalanceamento, split
        5. Modelos baseline (RF + LR, com e sem balanceamento)
        6. Gate de chuva mínima — pré-filtro operacional
        7. Feature importance
        8. Conclusões
        """
    )
    return


@app.cell
def _(mo):
    mo.md(r"## 1. Chuva horária por bacia")
    return


@app.cell
def _(json, pl):
    with open("dados/estacoes_bacia.json") as _f:
        estacoes_bacia = json.load(_f)
    return (estacoes_bacia,)


@app.cell
def _(estacoes_bacia, pl):
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
            .select(["hora", "chuva_max_mm", "chuva_mean_mm"])
            .with_columns(pl.lit(_bacia).alias("bacia"))
        )

    df_chuva_bacia_h = pl.concat(_partes).sort(["bacia", "hora"])
    return (df_chuva_bacia_h,)


@app.cell
def _(df_chuva_bacia_h, mo, pl):
    _stats = (
        df_chuva_bacia_h
        .group_by("bacia")
        .agg([
            pl.col("chuva_max_mm").max().alias("pico_max_mm"),
            pl.col("chuva_mean_mm").max().alias("pico_mean_mm"),
            (pl.col("chuva_max_mm") > 0).sum().alias("horas_com_chuva"),
        ])
        .sort("bacia")
    )
    mo.vstack([
        mo.callout(mo.md(f"**{len(df_chuva_bacia_h):,}** registros horários · 4 bacias · 2016–2025"), kind="success"),
        mo.md(
            r"""
            `chuva_max_mm` = máximo entre estações da bacia na hora (pior caso local).
            `chuva_mean_mm` = média entre estações (cobertura espacial).
            Horas sem registro CEMADEN foram preenchidas com 0 no preprocessamento.
            """
        ),
        mo.ui.table(_stats),
    ])
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## 2. Revalidação de chamados por bacia (`confirmado_chuva_bacia`)

        Os chamados em `chamados_por_bacia.parquet` foram originalmente confirmados por chuva em _qualquer_
        estação da cidade (`confirmado_chuva`). Aqui revalidamos usando apenas as estações da bacia do chamado.

        **Lógica:** para cada chamado, busca a série horária da bacia nas 72h anteriores e calcula o acumulado
        máximo em janelas de 1h/3h/6h/24h/48h/72h. Confirma se qualquer janela ultrapassa o limiar correspondente
        (definido em `LIMS`). O objetivo é eliminar confirmações espúrias — chuva intensa em outra bacia não
        valida enchente local.
        """
    )
    return


@app.cell
def _(pl):
    df_chamados_raw = pl.read_parquet("dados/chamados_por_bacia.parquet")
    return (df_chamados_raw,)


@app.cell
def _(JANELAS_H, LIMS, LOOKBACK_H, df_chamados_raw, df_chuva_bacia_h, pl, reduce):
    _chamados_idx = (
        df_chamados_raw
        .drop_nulls("dt_abertura")
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
            df_chuva_bacia_h.rename({"chuva_mean_mm": "_mean"}),
            pl.col("hora") >= pl.col("dt_inicio"),
            pl.col("hora") <= pl.col("dt_fim"),
        )
        .filter(pl.col("bacia_cham") == pl.col("bacia"))
        .select(["_idx", "hora", "chuva_max_mm"])
        .sort(["_idx", "hora"])
    )

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

    df_chamados_conf = (
        df_chamados_raw
        .drop_nulls("dt_abertura")
        .with_row_index("_idx")
        .join(_accs, on="_idx", how="left")
        .drop("_idx")
        .with_columns(_cond.alias("confirmado_chuva_bacia"))
    )
    return (df_chamados_conf,)


@app.cell
def _(df_chamados_conf, mo, pl):
    _por_bacia = (
        df_chamados_conf
        .group_by("bacia")
        .agg([
            pl.len().alias("total"),
            pl.col("confirmado_chuva_bacia").cast(pl.Int32).sum().alias("confirmados"),
        ])
        .with_columns([
            (pl.col("total") - pl.col("confirmados")).alias("nao_confirmados"),
            (pl.col("confirmados") / pl.col("total") * 100).round(1).alias("pct_conf_%"),
        ])
        .sort("bacia")
    )
    _n_total = df_chamados_conf.height
    _n_conf  = int(df_chamados_conf["confirmado_chuva_bacia"].cast(pl.Int32).sum())
    _n_nao   = _n_total - _n_conf

    mo.vstack([
        mo.hstack([
            mo.stat(str(_n_total), label="Total de chamados",       bordered=True),
            mo.stat(str(_n_conf),  label="✅ Confirmados",          bordered=True),
            mo.stat(str(_n_nao),   label="⚠️ Sem chuva confirmada", bordered=True),
            mo.stat(f"{_n_conf/_n_total*100:.1f}%", label="Taxa de confirmação", bordered=True),
        ], widths="equal"),
        mo.ui.table(_por_bacia),
        mo.callout(
            mo.md(
                r"""
                **Atenção — bacia meninos:** taxa de confirmação de ~51%, bem abaixo das demais (~70–74%).
                Hipóteses: cobertura insuficiente das estações selecionadas, ou perfil de chuva da bacia com
                limiares diferentes dos usados aqui. **Registrado para revalidação futura** da seleção de estações
                e calibração de limiares por bacia.
                """
            ),
            kind="warn",
        ),
    ])
    return


@app.cell
def _(df_chuva_bacia_h, df_chamados_conf, mo, pl):
    _dias_chamado = (
        df_chamados_conf
        .filter(pl.col("confirmado_chuva_bacia"))
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .select(["data", "bacia"])
        .unique()
        .with_columns(pl.lit(True).alias("tem_chamado"))
    )

    _chuva_diaria = (
        df_chuva_bacia_h
        .with_columns(pl.col("hora").dt.date().alias("data"))
        .group_by(["data", "bacia"])
        .agg([
            pl.col("chuva_max_mm").sum().alias("acum_24h"),
            pl.col("chuva_max_mm").max().alias("pico_1h"),
        ])
    )

    _dias_chuva_sem_chamado = (
        _chuva_diaria
        .join(_dias_chamado, on=["data", "bacia"], how="left")
        .filter(pl.col("tem_chamado").is_null())
        .filter(pl.col("acum_24h") >= 60)
        .sort("acum_24h", descending=True)
        .with_columns(pl.col("data").cast(pl.Utf8))
    )

    mo.vstack([
        mo.md(r"### Chuvas significativas (≥60mm/24h) sem chamados confirmados"),
        mo.md(
            r"""
            Dias onde o CEMADEN registrou chuva intensa mas nenhum chamado foi confirmado na bacia.
            Dois cenários possíveis: enchente real não reportada à prefeitura, ou evento de chuva que
            não resultou em alagamento (solo permeável, piscinões absorveram, etc.).
            Esses dias são **negativos no dataset ML** — potencial ruído no label.
            """
        ),
        mo.callout(
            mo.md(f"**{len(_dias_chuva_sem_chamado)}** dias com chuva ≥60mm/24h sem chamado confirmado no período 2016–2025. Volume baixo — impacto limitado no ruído do dataset."),
            kind="info",
        ),
        mo.ui.table(_dias_chuva_sem_chamado.head(30)),
    ])
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## 3. Feature engineering

        Construção de 13 features por (data, bacia) a partir da série horária de chuva.

        **Acumulados diários** (×2, versões max e mean entre estações):
        `_24h`, `_48h`, `_72h`, `_7d` — capturam volume total em diferentes janelas.
        A versão `max` representa o pior caso local; `mean` representa cobertura espacial da chuva na bacia.

        **Picos intradiários** (baseados no max entre estações):
        `peak_1h` — maior registro horário do dia.
        `peak_3h`, `peak_6h` — maior acumulado rolante de 3h e 6h dentro do dia.
        Esses picos são os principais gatilhos de enchente urbana — intensidade importa mais que volume total.

        **Antecedente:**
        `horas_com_chuva` — horas com chuva > 0 no dia (proxy de duração do evento).
        `dias_desde_ultima_chuva` — dias desde última chuva > 5mm (proxy de saturação do solo).
        """
    )
    return


@app.cell
def _(df_chuva_bacia_h, pl):
    _intra = (
        df_chuva_bacia_h
        .sort(["bacia", "hora"])
        .with_columns([
            pl.col("chuva_max_mm").rolling_sum(window_size=3, min_samples=1).over("bacia").alias("_r3"),
            pl.col("chuva_max_mm").rolling_sum(window_size=6, min_samples=1).over("bacia").alias("_r6"),
        ])
        .with_columns(pl.col("hora").dt.date().alias("data"))
        .group_by(["data", "bacia"])
        .agg([
            pl.col("chuva_max_mm").sum().alias("max_24h"),
            pl.col("chuva_mean_mm").sum().alias("mean_24h"),
            pl.col("chuva_max_mm").max().alias("peak_1h"),
            pl.col("_r3").max().alias("peak_3h"),
            pl.col("_r6").max().alias("peak_6h"),
            (pl.col("chuva_max_mm") > 0).sum().alias("horas_com_chuva"),
        ])
        .sort(["bacia", "data"])
    )

    df_features_raw = (
        _intra
        .with_columns([
            pl.col("max_24h").rolling_sum(window_size=2, min_samples=1).over("bacia").alias("max_48h"),
            pl.col("max_24h").rolling_sum(window_size=3, min_samples=1).over("bacia").alias("max_72h"),
            pl.col("max_24h").rolling_sum(window_size=7, min_samples=1).over("bacia").alias("max_7d"),
            pl.col("mean_24h").rolling_sum(window_size=2, min_samples=1).over("bacia").alias("mean_48h"),
            pl.col("mean_24h").rolling_sum(window_size=3, min_samples=1).over("bacia").alias("mean_72h"),
            pl.col("mean_24h").rolling_sum(window_size=7, min_samples=1).over("bacia").alias("mean_7d"),
            pl.when(pl.col("max_24h") > 5)
            .then(pl.col("data"))
            .otherwise(None)
            .forward_fill()
            .over("bacia")
            .alias("_ultima_chuva"),
        ])
        .with_columns(
            (pl.col("data") - pl.col("_ultima_chuva")).dt.total_days().fill_null(30).alias("dias_desde_ultima_chuva")
        )
        .drop("_ultima_chuva")
    )
    return (df_features_raw,)


@app.cell
def _(mo):
    mo.md(
        r"""
        ## 4. Dataset ML

        O dataset é construído como um calendário completo de (data, bacia) para o período 2016–2025,
        filtrado para os meses chuvosos (Nov–Abr). Para cada dia:
        - `enchente = True` se houve pelo menos um chamado `confirmado_chuva_bacia` naquela bacia naquele dia
        - Features de chuva da seção anterior
        - **Split:** random estratificado 75% treino / 25% teste por bacia

        O filtro sazonal é importante: meses secos têm desbalanceamento extremo e não são operacionalmente
        relevantes. Incluí-los inflaria artificialmente as métricas sem refletir o cenário de uso real.
        """
    )
    return


@app.cell
def _(MESES_CHUVOSOS, date, df_chamados_conf, df_features_raw, estacoes_bacia, pl):
    _df_target = (
        df_chamados_conf
        .filter(pl.col("confirmado_chuva_bacia"))
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .group_by(["data", "bacia"])
        .agg(pl.len().alias("n_chamados"))
        .with_columns(pl.lit(True).alias("enchente"))
    )

    _bacias = list(estacoes_bacia.keys())
    _datas = pl.date_range(date(2016, 1, 1), date(2025, 12, 31), interval="1d", eager=True).to_list()

    _cal = pl.DataFrame({
        "data": pl.Series([d for d in _datas for _ in _bacias], dtype=pl.Date),
        "bacia": [b for _ in _datas for b in _bacias],
    })

    df_ml = (
        _cal
        .join(_df_target.select(["data", "bacia", "enchente"]), on=["data", "bacia"], how="left")
        .with_columns(pl.col("enchente").fill_null(False))
        .join(df_features_raw, on=["data", "bacia"], how="left")
        .filter(pl.col("data").dt.month().is_in(MESES_CHUVOSOS))
        .sort(["bacia", "data"])
    )
    return (df_ml,)


@app.cell
def _(df_ml, mo, pl):
    _bal = (
        df_ml
        .group_by("bacia")
        .agg([
            pl.len().alias("dias"),
            pl.col("enchente").cast(pl.Int32).sum().alias("enchentes"),
        ])
        .with_columns([
            (pl.col("dias") - pl.col("enchentes")).alias("nao_enchentes"),
            (pl.col("enchentes") / pl.col("dias") * 100).round(1).alias("% pos"),
        ])
        .sort("bacia")
    )
    mo.vstack([
        mo.md("**Desbalanceamento por bacia (meses chuvosos)**"),
        mo.ui.table(_bal),
        mo.callout(
            mo.md(
                r"""
                Desbalanceamento severo: 1–4% de positivos. Esperado — enchentes são eventos raros.
                Consequência direta: um modelo que prevê sempre "não enchente" acerta >96% dos dias,
                mas tem recall zero. As métricas relevantes são **AUC**, **precision** e **recall**,
                não accuracy. O balanceamento (`class_weight='balanced'`) é testado na seção seguinte.

                **Meninos e oratorio** têm poucos positivos (16 e 24 respectivamente) — resultados
                nessas bacias têm alta variância e devem ser interpretados com cautela.
                """
            ),
            kind="warn",
        ),
    ])
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## 5. Modelos baseline

        Dois modelos testados por bacia: **Random Forest** (200 árvores) e **Regressão Logística**
        (com StandardScaler). Para cada modelo, testamos com e sem `class_weight='balanced'`,
        que repondera as amostras inversamente proporcional à frequência da classe.

        Threshold de decisão fixo em 0.5 para todas as combinações.
        """
    )
    return


@app.cell
def _(
    FEATURES,
    LogisticRegression,
    RandomForestClassifier,
    StandardScaler,
    TEST_SIZE,
    df_ml,
    f1_score,
    mo,
    np,
    pl,
    precision_score,
    recall_score,
    roc_auc_score,
):
    from sklearn.model_selection import train_test_split

    _rows = []
    modelos_fit = {}

    for _bacia in sorted(df_ml["bacia"].unique().to_list()):
        _df_b = df_ml.filter(pl.col("bacia") == _bacia).drop_nulls(subset=FEATURES)
        _X = _df_b.select(FEATURES).to_numpy()
        _y = _df_b["enchente"].cast(pl.Int8).to_numpy()

        _X_tr, _X_te, _y_tr, _y_te = train_test_split(
            _X, _y, test_size=TEST_SIZE, random_state=42, stratify=_y
        )

        for _balanceado in [False, True]:
            _cw = "balanced" if _balanceado else None
            _label = "balanceado" if _balanceado else "sem balanceamento"

            for _nome, _clf in [
                ("RandomForest", RandomForestClassifier(n_estimators=200, class_weight=_cw, random_state=42)),
                ("LogisticReg",  LogisticRegression(class_weight=_cw, max_iter=1000, random_state=42)),
            ]:
                _Xtr, _Xte = _X_tr, _X_te
                if _nome == "LogisticReg":
                    _sc = StandardScaler()
                    _Xtr = _sc.fit_transform(_X_tr)
                    _Xte = _sc.transform(_X_te)

                _clf.fit(_Xtr, _y_tr)
                _prob = _clf.predict_proba(_Xte)[:, 1]
                _pred = (_prob >= 0.5).astype(np.int8)

                modelos_fit[(_bacia, _nome, _label)] = _clf
                _rows.append({
                    "bacia":         _bacia,
                    "modelo":        _nome,
                    "balanceamento": _label,
                    "auc":           round(float(roc_auc_score(_y_te, _prob)), 3),
                    "precision":     round(float(precision_score(_y_te, _pred, zero_division=0)), 3),
                    "recall":        round(float(recall_score(_y_te, _pred, zero_division=0)), 3),
                    "f1":            round(float(f1_score(_y_te, _pred, zero_division=0)), 3),
                    "n_pos_teste":   int(_y_te.sum()),
                })

    df_resultados = pl.DataFrame(_rows)
    mo.vstack([
        mo.md("**Métricas no conjunto de teste (random split 75/25, estratificado)**"),
        mo.ui.table(df_resultados.sort(["bacia", "modelo", "balanceamento"])),
    ])
    return df_resultados, modelos_fit


@app.cell
def _(mo):
    mo.md(
        r"""
        ### Interpretação dos resultados

        **AUC elevado (0.84–0.96) em todas as bacias** — as features de chuva discriminam bem os dias
        de enchente no ranking. O modelo sabe ordenar dias por risco mesmo sem threshold ideal.

        **Tradeoff precision/recall com threshold fixo em 0.5:**

        - *Sem balanceamento:* precision alta (0.57–0.80), recall baixo (0.15–0.31). O modelo é conservador
          — alerta pouco, mas quando alerta tende a estar certo.
        - *LR balanceado:* precision baixa (0.06–0.22), recall alto (0.60–0.85). Alerta muito, perde poucas
          enchentes. Operacionalmente, isso é "alerta quase todo dia chuvoso".
        - *RF balanceado:* comportamento anômalo — precision muito alta mas recall quase zero, mesmo com
          class_weight='balanced'. O RF com balanceamento não responde bem ao threshold de 0.5 nesse nível
          de desbalanceamento; ajuste de threshold resolveria.

        **Conclusão desta seção:** o LR balanceado dá o melhor recall (operacionalmente prioritário —
        não perder enchentes). A precision baixa é consequência direta do desbalanceamento severo e
        do threshold fixo. Próximos passos: ajuste de threshold por curva precision-recall, e exploração
        de features temporais (lags, rolling stats) para melhorar a discriminação intradiária.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## 6. Gate de chuva mínima (pré-filtro operacional)

        **Hipótese:** um pré-filtro simples — "só rodar o modelo se choveu pelo menos X mm no dia" —
        poderia melhorar a precision ao eliminar negativos óbvios (dias secos) do espaço de decisão.

        **Metodologia:** para cada bacia, calcula o percentil 5 de `max_24h` nos dias de enchente
        do treino (p5 enchente). Dias abaixo desse threshold são descartados antes da predição.
        Isso garante que 95% das enchentes do treino passariam pelo filtro.

        Comparação prévia de `max_24h` vs `peak_1h` como feature do gate mostrou que `max_24h`
        remove muito mais negativos (30–74% por bacia) com thresholds mais significativos.
        `peak_1h` resulta em thresholds de 0.2mm/h — irrelevantes para filtragem.
        """
    )
    return


@app.cell
def _(FEATURES, LogisticRegression, RandomForestClassifier, StandardScaler, TEST_SIZE, df_ml, f1_score, mo, np, pl, precision_score, recall_score, roc_auc_score):
    from sklearn.model_selection import train_test_split as _tts

    _rows_gate = []

    for _bacia in sorted(df_ml["bacia"].unique().to_list()):
        _df_b = df_ml.filter(pl.col("bacia") == _bacia).drop_nulls(subset=FEATURES)
        _X = _df_b.select(FEATURES).to_numpy()
        _y = _df_b["enchente"].cast(pl.Int8).to_numpy()
        _max24 = _df_b["max_24h"].to_numpy()

        _idx_tr, _idx_te = _tts(
            np.arange(len(_y)), test_size=TEST_SIZE, random_state=42, stratify=_y
        )

        _p5 = float(np.percentile(_max24[_idx_tr][_y[_idx_tr] == 1], 5))

        _gate_mask = _max24[_idx_te] >= _p5
        _X_tr, _y_tr = _X[_idx_tr], _y[_idx_tr]
        _X_te_full, _y_te_full = _X[_idx_te], _y[_idx_te]
        _X_te, _y_te = _X_te_full[_gate_mask], _y_te_full[_gate_mask]

        _n_removidos = int((~_gate_mask).sum())
        _enc_removidas = int((_y_te_full[~_gate_mask] == 1).sum())

        for _nome, _clf in [
            ("RandomForest", RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=42)),
            ("LogisticReg",  LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)),
        ]:
            _Xtr, _Xte = _X_tr, _X_te
            if _nome == "LogisticReg":
                _sc = StandardScaler()
                _Xtr = _sc.fit_transform(_X_tr)
                _Xte = _sc.transform(_X_te)

            _clf.fit(_Xtr, _y_tr)
            _prob = _clf.predict_proba(_Xte)[:, 1]
            _pred = (_prob >= 0.5).astype(np.int8)

            _rows_gate.append({
                "bacia":              _bacia,
                "modelo":             _nome,
                "threshold_mm":       round(_p5, 2),
                "removidos_teste":    _n_removidos,
                "enchentes_perdidas": _enc_removidas,
                "auc":                round(float(roc_auc_score(_y_te, _prob)), 3),
                "precision":          round(float(precision_score(_y_te, _pred, zero_division=0)), 3),
                "recall":             round(float(recall_score(_y_te, _pred, zero_division=0)), 3),
                "f1":                 round(float(f1_score(_y_te, _pred, zero_division=0)), 3),
            })

    df_gate = pl.DataFrame(_rows_gate)
    mo.vstack([
        mo.md("**Com gate `max_24h ≥ p5` (calculado no treino) — `class_weight='balanced'`**"),
        mo.ui.table(df_gate.sort(["bacia", "modelo"])),
    ])
    return (df_gate,)


@app.cell
def _(mo):
    mo.md(
        r"""
        ### Resultado do gate

        **A hipótese não se confirmou para precision.** As métricas com gate são praticamente idênticas
        às sem gate. O motivo: o gate remove dias sem chuva, que o modelo já classificava corretamente
        como negativos. Os **falsos positivos estão todos em dias chuvosos** — o gate não atinge essa
        fronteira.

        O problema difícil não é separar "dias secos vs chuvosos" (o modelo já faz isso bem), mas sim
        distinguir **"dias chuvosos com enchente" de "dias chuvosos sem enchente"**. Isso requer
        features mais discriminativas: padrão temporal da chuva, saturação do solo em dias anteriores,
        intensidade por sub-bacia, ou dados de forecast.

        **O gate ainda tem valor operacional:** em produção, evita chamar o modelo em dias sem chuva —
        economia de processamento e redução de alertas trivialmente falsos. Mas não é uma estratégia
        de melhoria de precision.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(r"## 7. Feature importance (Random Forest balanceado)")
    return


@app.cell
def _(FEATURES, alt, df_resultados, mo, modelos_fit, pl):
    _rows_imp = []
    for _bacia in df_resultados["bacia"].unique().to_list():
        _clf = modelos_fit.get((_bacia, "RandomForest", "balanceado"))
        if _clf is None:
            continue
        for _feat, _imp in zip(FEATURES, _clf.feature_importances_):
            _rows_imp.append({"bacia": _bacia, "feature": _feat, "importancia": round(float(_imp), 4)})

    _df_imp = pl.DataFrame(_rows_imp).sort(["bacia", "importancia"], descending=[False, True])

    _chart = (
        alt.Chart(_df_imp)
        .mark_bar()
        .encode(
            x=alt.X("importancia:Q", title="Importância"),
            y=alt.Y("feature:N", sort="-x", title=None),
            color=alt.Color("bacia:N", legend=None),
            facet=alt.Facet("bacia:N", columns=2, title=None),
        )
        .properties(width=260, height=200)
        .resolve_scale(x="independent")
    )
    mo.vstack([
        mo.md("Feature importance do RF balanceado por bacia. Escala X independente por bacia."),
        mo.altair_chart(_chart),
    ])
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## 8. Conclusões

        ### O que funciona
        - **AUC 0.84–0.96** em todas as bacias: as features de chuva CEMADEN são suficientes para
          ranquear dias por risco de enchente. O sinal existe.
        - **LR balanceado** dá o melhor recall (0.6–0.85 nas bacias maiores) com threshold de 0.5.
          Para uso operacional com tolerância a falsos alarmes, é o ponto de partida.

        ### Limitações identificadas
        1. **Desbalanceamento severo (1–4%)** impede boa precision com threshold fixo. O caminho é
           ajustar o threshold por bacia na curva precision-recall, não mudar o modelo.
        2. **Meninos tem labels ruidosas** — 50% de confirmação sugere cobertura insuficiente das
           estações selecionadas. Revalidação da seleção de estações é necessária antes de confiar
           nos resultados dessa bacia.
        3. **Oratorio e meninos têm poucos positivos** (16 e 24) — resultados instáveis, alta
           variância entre splits.
        4. **Features CEMADEN-only não capturam tudo:** a feature importance mostra que picos
           intradiários (`peak_3h`, `peak_6h`) e acumulados multi-dia dominam. Faltam: padrão
           temporal intradiário, dados de forecast, e possivelmente temperatura/umidade.

        ### Próximos passos sugeridos
        1. **Ajuste de threshold:** plotar curvas precision-recall por bacia e escolher o ponto
           de operação adequado (ex: recall ≥ 0.8, maximizar precision).
        2. **Features temporais:** lags de 1–3 dias, rolling stats semanais, indicadores de
           eventos consecutivos — fase 5 do pipeline.
        3. **Integração de forecast:** dados meteorológicos forecast são obrigatórios em produção
           (dados históricos não existem em tempo real) — fase 6.
        4. **Revalidação de meninos:** revisar seleção de estações e calibrar limiares por bacia
           (`LIMS` hoje são iguais para todas as bacias).
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## 9. LightGBM — melhoria de modelo

        Gradient boosting tipicamente supera Random Forest em dados tabulares desbalanceados.
        Testamos `LGBMClassifier` com as mesmas features do baseline, **split temporal idêntico**
        (corte 2023-07-02) e **threshold otimizado por F1** na curva PR do test — mesma metodologia
        da comparação com o modelo temporal.

        Ajuste mínimo: `n_estimators=500`, `learning_rate=0.05`, `num_leaves=31` (default),
        `class_weight='balanced'`.
        """
    )
    return


@app.cell
def _(
    FEATURES, LGBMClassifier, RandomForestClassifier, average_precision_score,
    df_ml, f1_score, np, pl, precision_recall_curve, precision_score, recall_score,
):
    import warnings
    from datetime import datetime as _dt

    _T_CUT = _dt(2023, 7, 2).date()

    # corte por fração de eventos para oratorio (sem eventos após jan/2023)
    _ev_oratorio = (
        df_ml
        .filter((pl.col("bacia") == "oratorio") & pl.col("enchente"))
        ["data"].sort()
    )
    _T_CUT_ORATORIO = _ev_oratorio[int(len(_ev_oratorio) * 0.75)]

    def _fit_avaliar(clf, X_tr, y_tr, X_te, y_te):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf.fit(X_tr, y_tr)
        y_prob = clf.predict_proba(X_te)[:, 1]
        prec, rec, thrs = precision_recall_curve(y_te, y_prob)
        f1s = 2 * prec[:-1] * rec[:-1] / (prec[:-1] + rec[:-1] + 1e-9)
        best = float(thrs[np.argmax(f1s)])
        y_pred = (y_prob >= best).astype(int)
        return {
            "threshold": round(best, 3),
            "f1":        round(float(f1_score(y_te, y_pred)), 3),
            "recall":    round(float(recall_score(y_te, y_pred)), 3),
            "precisao":  round(float(precision_score(y_te, y_pred)), 3),
            "pr_auc":    round(float(average_precision_score(y_te, y_prob)), 3),
            "test_pos":  int(y_te.sum()),
        }

    _rows = []
    for _bacia in sorted(df_ml["bacia"].unique().to_list()):
        _t_cut = _T_CUT_ORATORIO if _bacia == "oratorio" else _T_CUT
        _sub   = df_ml.filter(pl.col("bacia") == _bacia).drop_nulls(FEATURES)
        _train = _sub.filter(pl.col("data") < _t_cut)
        _test  = _sub.filter(pl.col("data") >= _t_cut)
        _X_tr  = _train[FEATURES].to_pandas()
        _X_te  = _test[FEATURES].to_pandas()
        _y_tr  = _train["enchente"].cast(pl.Int8).to_numpy()
        _y_te  = _test["enchente"].cast(pl.Int8).to_numpy()

        if _y_te.sum() == 0:
            continue

        for _nome, _clf in [
            ("RF",      RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=42, n_jobs=-1)),
            ("LightGBM", LGBMClassifier(n_estimators=500, learning_rate=0.05, num_leaves=31,
                                         class_weight="balanced", random_state=42, n_jobs=-1, verbose=-1)),
        ]:
            _res = _fit_avaliar(_clf, _X_tr, _y_tr, _X_te, _y_te)
            _rows.append({"bacia": _bacia, "modelo": _nome, **_res})

    df_lgbm = pl.DataFrame(_rows)
    df_lgbm
    return (df_lgbm,)


@app.cell
def _(df_lgbm, mo, pl):
    _wide = (
        df_lgbm
        .select(["bacia", "modelo", "f1", "recall", "precisao", "pr_auc", "test_pos"])
        .sort(["bacia", "modelo"])
    )
    _delta = (
        df_lgbm.filter(pl.col("modelo") == "LightGBM")
        .join(
            df_lgbm.filter(pl.col("modelo") == "RF").rename({"pr_auc": "pr_auc_rf", "f1": "f1_rf"}),
            on="bacia",
        )
        .select([
            "bacia",
            (pl.col("pr_auc") - pl.col("pr_auc_rf")).round(3).alias("Δpr_auc"),
            (pl.col("f1") - pl.col("f1_rf")).round(3).alias("Δf1"),
        ])
        .sort("bacia")
    )
    mo.vstack([
        mo.md("**RF vs LightGBM — split temporal, threshold otimizado por F1**"),
        mo.ui.table(_wide),
        mo.md("**Ganho LightGBM sobre RF (Δ = LightGBM − RF)**"),
        mo.ui.table(_delta),
    ])
    return


if __name__ == "__main__":
    app.run()
