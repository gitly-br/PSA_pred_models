import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    import marimo as mo
    import plotly.graph_objects as go

    return go, mo, pl


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Fase 2: Validação Regional de Estações CEMADEN

    Objetivo: determinar quais estações CEMADEN são relevantes para cada bacia hidrográfica,
    usando eventos de enchente confirmados como âncora.

    ## Inventário de estações

    Primeiro passo: entender quais estações existem, quando estiveram ativas e qual a qualidade
    de cobertura de cada uma. Inclui a análise da série **A** (original) vs série **G** (segunda
    rede), que têm nomes e coordenadas distintas apesar de compartilharem o prefixo do código.
    """)
    return


@app.cell
def _():
    import json as _json

    with open("dados/sub-bacias.geojson") as _f:
        _gj = _json.load(_f)

    # Apenas sub-bacias mapeadas para o modelo
    geojson_bacias = {
        "type": "FeatureCollection",
        "features": [f for f in _gj["features"] if f["properties"].get("MODELO")],
    }

    with open("dados/Areas_alagaveis.geojson") as _f:
        geojson_alagaveis = _json.load(_f)
    return geojson_alagaveis, geojson_bacias


@app.cell(hide_code=True)
def _(mo):
    btn_cemaden = mo.ui.run_button(label="Carregar CEMADEN")
    btn_cemaden
    return (btn_cemaden,)


@app.cell
def _(btn_cemaden, mo, pl):
    mo.stop(
        not btn_cemaden.value,
        mo.callout(mo.md("Clique em **Carregar CEMADEN** para iniciar."), kind="info"),
    )

    # Lazy scan — agrega sem carregar linhas na memória
    df_inventario = (
        pl.scan_parquet("dados/cemaden_abcd.parquet")
        .group_by(["municipio", "codEstacao", "nomeEstacao", "latitude", "longitude"])
        .agg([
            pl.col("dt").min().alias("primeira_leitura"),
            pl.col("dt").max().alias("ultima_leitura"),
            pl.col("dt").dt.truncate("1h").n_unique().alias("horas_com_leitura"),
        ])
        .with_columns([
            pl.col("codEstacao").str.extract(r"([A-Z])$").alias("serie"),
            (
                (pl.col("ultima_leitura") - pl.col("primeira_leitura"))
                .dt.total_hours() + 1
            ).alias("horas_esperadas"),
        ])
        .with_columns(
            (pl.col("horas_com_leitura") / pl.col("horas_esperadas") * 100)
            .round(1)
            .alias("cobertura_pct"),
        )
        .sort("codEstacao")
        .collect()
    )
    return (df_inventario,)


@app.cell(hide_code=True)
def _(df_inventario, geojson_alagaveis, geojson_bacias, go, mo):
    # --- helpers ---
    def _polygon_trace(features, color_fill, color_line, name, opacity=0.3):
        """Converte uma lista de features GeoJSON em um trace Scattermapbox preenchido."""
        lats, lons = [], []
        for feat in features:
            geom = feat["geometry"]
            polys = (
                geom["coordinates"]
                if geom["type"] == "MultiPolygon"
                else [geom["coordinates"]]
            )
            for poly in polys:
                for ring in poly:
                    for coord in ring:
                        lons.append(coord[0])
                        lats.append(coord[1])
                    lats.append(None)
                    lons.append(None)
        return go.Scattermapbox(
            lat=lats,
            lon=lons,
            mode="lines",
            fill="toself",
            fillcolor=color_fill,
            line=dict(color=color_line, width=1),
            name=name,
            hoverinfo="skip",
        )

    # --- paleta ---
    _BACIAS = {
        "meninos":     ("#66BB6A", "rgba(102,187,106,0.25)"),
        "oratorio":    ("#AB47BC", "rgba(171,71,188,0.25)"),
        "tamanduatei": ("#42A5F5", "rgba(66,165,245,0.25)"),
        "guarara":     ("#FFA726", "rgba(255,167,38,0.25)"),
    }
    _NOMES = {
        "meninos": "Meninos", "oratorio": "Oratório",
        "tamanduatei": "Tamanduateí", "guarara": "Guarará",
    }

    traces = []

    # Camada 1 — polígonos das bacias
    for _modelo, (_cor, _fill) in _BACIAS.items():
        _feats = [
            f for f in geojson_bacias["features"]
            if f["properties"]["MODELO"] == _modelo
        ]
        traces.append(_polygon_trace(_feats, _fill, _cor, _NOMES[_modelo]))

    # Camada 2 — áreas alagáveis
    traces.append(_polygon_trace(
        geojson_alagaveis["features"],
        "rgba(239,83,80,0.2)", "#EF5350",
        "Área alagável",
    ))

    # Camada 3 — estações CEMADEN
    _CORES_MUN = {
        "SANTO ANDRÉ":           "#1565C0",
        "MAUÁ":                  "#2E7D32",
        "SÃO BERNARDO DO CAMPO": "#6A1B9A",
        "SÃO CAETANO DO SUL":    "#E65100",
    }
    _SIMBOLOS_SERIE = {"A": "circle", "G": "circle-open"}

    for (_mun, _serie), _df_s in df_inventario.group_by(
        ["municipio", "serie"], maintain_order=True
    ):
        _hover = [
            f"<b>{row['nomeEstacao']}</b><br>"
            f"{row['codEstacao']} · {row['municipio']} · Série {_serie}<br>"
            f"Cobertura: {row['cobertura_pct']}%<br>"
            f"{str(row['primeira_leitura'])[:10]} → {str(row['ultima_leitura'])[:10]}"
            for row in _df_s.iter_rows(named=True)
        ]
        _sizes = [max(10, v / 4) for v in _df_s["cobertura_pct"].to_list()]
        traces.append(go.Scattermapbox(
            lat=_df_s["latitude"].to_list(),
            lon=_df_s["longitude"].to_list(),
            mode="markers",
            marker=dict(
                size=_sizes,
                color=_CORES_MUN.get(_mun, "#888"),
                opacity=0.85,
            ),
            text=_hover,
            hoverinfo="text",
            name=f"{_mun.title()} · Série {_serie}",
        ))

    _fig = go.Figure(traces)
    _fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_zoom=11,
        mapbox_center={"lat": -23.69, "lon": -46.52},
        height=580,
        title="Estações CEMADEN × Bacias × Áreas alagáveis — ABCD",
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        legend=dict(
            title="Camadas",
            bgcolor="rgba(255,255,255,0.85)",
            borderwidth=1,
        ),
        dragmode="pan",
    )

    _tabela = mo.ui.table(
        df_inventario.select([
            "municipio", "codEstacao", "nomeEstacao", "serie",
            "primeira_leitura", "ultima_leitura",
            "horas_com_leitura", "horas_esperadas", "cobertura_pct",
        ]).sort(["municipio", "codEstacao"]),
        label=f"{len(df_inventario)} estações CEMADEN — ABCD",
    )

    mo.vstack([mo.ui.plotly(_fig, config={"scrollZoom": True, "modeBarButtonsToRemove": ["select2d", "lasso2d"]}), _tabela])
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Correlação estação × bacia

    Para cada par (bacia, estação), medimos o AUC: quão bem o acumulado de chuva
    naquela estação separa dias com chamados de enchente de dias chuvosos sem chamados.
    """)
    return


@app.cell
def _(mo, pl):
    _path = "dados/chamados_por_bacia.parquet"
    try:
        df_chamados_bacia = pl.read_parquet(_path)
        _info = mo.callout(
            mo.md(f"**{len(df_chamados_bacia):,}** chamados 809.x carregados — "
                  f"{df_chamados_bacia['bacia'].n_unique()} bacias, "
                  f"{df_chamados_bacia['dt_abertura'].dt.year().min()}–"
                  f"{df_chamados_bacia['dt_abertura'].dt.year().max()}."),
            kind="success",
        )
    except FileNotFoundError:
        df_chamados_bacia = None
        _info = mo.callout(
            mo.md("Arquivo `dados/chamados_por_bacia.parquet` não encontrado. "
                  "Execute o export na **Fase 1** primeiro."),
            kind="danger",
        )
    _ = _info
    return (df_chamados_bacia,)


@app.cell
def _(btn_cemaden, mo, pl):
    mo.stop(not btn_cemaden.value)

    JANELAS_H = [1, 3, 6, 24, 48, 72]

    # --- Agregar para resolução horária (pesado, roda uma vez) ---
    df_horario = (
        pl.scan_parquet("dados/cemaden_abcd.parquet")
        .with_columns(pl.col("dt").dt.truncate("1h").alias("hora"))
        .group_by(["codEstacao", "hora"])
        .agg(pl.col("valor_mm").sum().alias("valor_mm"))
        .sort(["codEstacao", "hora"])
        .collect()
    )

    # --- Acumulados por estação (rolling sobre horas) ---
    _acc_frames = []
    for _h in JANELAS_H:
        _frame = (
            df_horario.lazy()
            .with_columns(
                pl.col("valor_mm")
                  .rolling_sum(window_size=_h, min_periods=1)
                  .over("codEstacao")
                  .alias(f"acc_{_h}h")
            )
            .select(["codEstacao", "hora", f"acc_{_h}h"])
            .collect()
        )
        _acc_frames.append(_frame)

    df_acc = _acc_frames[0]
    for _f in _acc_frames[1:]:
        df_acc = df_acc.join(_f, on=["codEstacao", "hora"], how="left")

    # Agregar por dia: max acumulado por estação
    df_acc_diario = (
        df_acc
        .with_columns(pl.col("hora").dt.date().alias("data"))
        .group_by(["codEstacao", "data"])
        .agg([pl.col(f"acc_{h}h").max().alias(f"acc_{h}h") for h in JANELAS_H])
    )
    return (df_acc_diario,)


@app.cell
def _(mo):
    sel_anos = mo.ui.range_slider(
        start=2016, stop=2025, step=1, value=[2016, 2025],
        label="Período", show_value=True,
    )
    lim_1h  = mo.ui.number(start=1,  stop=150, step=1, value=10,  label="1h (mm)")
    lim_3h  = mo.ui.number(start=1,  stop=200, step=1, value=15,  label="3h (mm)")
    lim_6h  = mo.ui.number(start=1,  stop=300, step=1, value=22,  label="6h (mm)")
    lim_24h = mo.ui.number(start=1,  stop=300, step=1, value=30,  label="24h (mm)")
    lim_48h = mo.ui.number(start=1,  stop=300, step=1, value=40,  label="48h (mm)")
    lim_72h = mo.ui.number(start=1,  stop=300, step=1, value=50,  label="72h (mm)")
    mo.vstack([
        sel_anos,
        mo.md("**Limiares de chuva por janela:**"),
        mo.hstack([lim_1h, lim_3h, lim_6h, lim_24h, lim_48h, lim_72h], widths="equal"),
    ])
    return lim_1h, lim_24h, lim_3h, lim_48h, lim_6h, lim_72h, sel_anos


@app.cell
def _(
    df_acc_diario,
    df_chamados_bacia,
    lim_1h,
    lim_24h,
    lim_3h,
    lim_48h,
    lim_6h,
    lim_72h,
    mo,
    pl,
    sel_anos,
):
    import numpy as np
    from sklearn.metrics import roc_auc_score

    mo.stop(df_chamados_bacia is None)

    _ano_ini, _ano_fim = sel_anos.value

    LIMS = {
        1: lim_1h.value, 3: lim_3h.value, 6: lim_6h.value,
        24: lim_24h.value, 48: lim_48h.value, 72: lim_72h.value,
    }

    # --- Filtrar por período selecionado ---
    _acc = df_acc_diario.filter(
        (pl.col("data").dt.year() >= _ano_ini) & (pl.col("data").dt.year() <= _ano_fim)
    )
    _chamados = df_chamados_bacia.filter(
        (pl.col("dt_abertura").dt.year() >= _ano_ini) & (pl.col("dt_abertura").dt.year() <= _ano_fim)
    )

    # --- Score diário: votos acima do limiar ---
    df_score = (
        _acc
        .with_columns(
            pl.sum_horizontal(
                *[(pl.col(f"acc_{h}h").fill_null(0) >= lim).cast(pl.Int8)
                  for h, lim in LIMS.items()]
            ).alias("votos")
        )
        .filter(pl.col("votos") > 0)
    )

    # --- Labels por (data, bacia) ---
    _dias_positivos = (
        _chamados
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .select(["data", "bacia"])
        .unique()
    )

    # --- AUC + cobertura por (bacia, estação) ---
    _bacias = _dias_positivos["bacia"].drop_nulls().unique().to_list()
    _rows = []

    for _bacia in sorted(_bacias):
        _pos = set(
            _dias_positivos.filter(pl.col("bacia") == _bacia)["data"].to_list()
        )
        _n_dias_pos = len(_pos)
        for _cod, _df_est in df_score.group_by("codEstacao"):
            _cod = _cod[0]
            _datas = _df_est["data"].to_list()
            _votos = _df_est["votos"].to_list()
            _labels = [1 if d in _pos else 0 for d in _datas]
            if sum(_labels) < 5 or sum(_labels) == len(_labels):
                continue
            _auc = roc_auc_score(_labels, _votos)
            _confirmados = sum(_labels)
            _cobertura = _confirmados / _n_dias_pos if _n_dias_pos > 0 else 0
            _auc_norm = max(0, (_auc - 0.5) * 2)
            _score_raw = (_auc_norm * _cobertura) ** 0.5
            _rows.append({
                "bacia": _bacia, "codEstacao": _cod,
                "auc": round(_auc, 3), "cobertura": round(_cobertura, 3),
                "score_raw": round(_score_raw, 4),
            })

    df_auc = pl.DataFrame(_rows)

    # Normalizar score pelo max observado por bacia
    df_auc = df_auc.with_columns(
        (pl.col("score_raw") / pl.col("score_raw").max().over("bacia"))
        .round(3)
        .alias("score")
    )

    _ = mo.callout(mo.md(f"Calculado para **{len(df_auc)}** pares (bacia × estação) — período {_ano_ini}–{_ano_fim}."), kind="success")
    return df_auc, df_score


@app.cell
def _(mo):
    d0_guarara     = mo.ui.number(start=1, stop=30, step=1, value=5,  label="d₀ guarará (km)")
    d0_meninos     = mo.ui.number(start=1, stop=30, step=1, value=6,  label="d₀ meninos (km)")
    d0_oratorio    = mo.ui.number(start=1, stop=30, step=1, value=6,  label="d₀ oratório (km)")
    d0_tamanduatei = mo.ui.number(start=1, stop=30, step=1, value=9,  label="d₀ tamanduateí (km)")
    mo.vstack([
        mo.md("**Demérito por distância** — `score_ajustado = score × exp(-(d/d₀)²)`"),
        mo.hstack([d0_guarara, d0_meninos, d0_oratorio, d0_tamanduatei], widths="equal"),
    ])
    return d0_guarara, d0_meninos, d0_oratorio, d0_tamanduatei


@app.cell
def _(df_auc, mo):
    _bacias = sorted(df_auc["bacia"].unique().to_list())
    sel_bacia = mo.ui.radio(options=_bacias, value=_bacias[0], label="Bacia", inline=True)
    return (sel_bacia,)


@app.cell
def _(df_chamados_bacia, mo, pl, sel_bacia):
    _ch = df_chamados_bacia.filter(pl.col("bacia") == sel_bacia.value) if df_chamados_bacia is not None else None
    _n_ch = len(_ch) if _ch is not None else 0
    _n_dias = _ch["dt_abertura"].dt.date().n_unique() if _ch is not None else 0
    mo.vstack([
        mo.callout(mo.md(
            f"### AUC por estação\n\n"
            f"Bacia **{sel_bacia.value}**: **{_n_ch}** chamados em **{_n_dias}** dias distintos"
        ), kind="info"),
        sel_bacia,
    ])
    return


@app.cell
def _(
    d0_guarara,
    d0_meninos,
    d0_oratorio,
    d0_tamanduatei,
    df_auc,
    df_chamados_bacia,
    df_inventario,
    df_score,
    geojson_alagaveis,
    geojson_bacias,
    go,
    mo,
    pl,
    sel_bacia,
):
    def _poly(features, color_fill, color_line, name):
        lats, lons = [], []
        for feat in features:
            geom = feat["geometry"]
            polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
            for poly in polys:
                for ring in poly:
                    for coord in ring:
                        lons.append(coord[0])
                        lats.append(coord[1])
                    lats.append(None)
                    lons.append(None)
        return go.Scattermapbox(
            lat=lats, lon=lons, mode="lines", fill="toself",
            fillcolor=color_fill, line=dict(color=color_line, width=1),
            name=name, hoverinfo="skip",
        )

    _BACIAS_COR = {
        "meninos":     ("#66BB6A", "rgba(102,187,106,0.25)"),
        "oratorio":    ("#AB47BC", "rgba(171,71,188,0.25)"),
        "tamanduatei": ("#42A5F5", "rgba(66,165,245,0.25)"),
        "guarara":     ("#FFA726", "rgba(255,167,38,0.25)"),
    }
    _NOMES = {"meninos": "Meninos", "oratorio": "Oratório",
              "tamanduatei": "Tamanduateí", "guarara": "Guarará"}

    _traces = []
    # Apenas a bacia selecionada destacada; demais muito transparentes
    for _m, (_c, _f) in _BACIAS_COR.items():
        _feats = [f for f in geojson_bacias["features"] if f["properties"]["MODELO"] == _m]
        if _m == sel_bacia.value:
            _traces.append(_poly(_feats, _f, _c, _NOMES[_m]))
        else:
            _traces.append(_poly(_feats, "rgba(200,200,200,0.08)", "#ccc", _NOMES[_m]))

    # Áreas alagáveis apenas dentro da bacia selecionada
    _feats_alag = [
        f for f in geojson_alagaveis["features"]
        if f["properties"].get("MODELO") == sel_bacia.value
    ]
    if not _feats_alag:
        _feats_alag = geojson_alagaveis["features"]
    _traces.append(_poly(_feats_alag, "rgba(239,83,80,0.2)", "#EF5350", "Área alagável"))

    import math as _math

    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = _math.radians(lat2 - lat1)
        dlon = _math.radians(lon2 - lon1)
        a = _math.sin(dlat / 2) ** 2 + _math.cos(_math.radians(lat1)) * _math.cos(_math.radians(lat2)) * _math.sin(dlon / 2) ** 2
        return R * 2 * _math.asin(_math.sqrt(a))

    # --- Centróide da bacia selecionada (média das coordenadas dos polígonos) ---
    _feats_bacia = [f for f in geojson_bacias["features"] if f["properties"]["MODELO"] == sel_bacia.value]
    _clats, _clons = [], []
    for _feat in _feats_bacia:
        _geom = _feat["geometry"]
        _polys = _geom["coordinates"] if _geom["type"] == "MultiPolygon" else [_geom["coordinates"]]
        for _poly in _polys:
            for _ring in _poly:
                for _coord in _ring:
                    _clons.append(_coord[0])
                    _clats.append(_coord[1])
    _centroide_lat = sum(_clats) / len(_clats) if _clats else -23.69
    _centroide_lon = sum(_clons) / len(_clons) if _clons else -46.52

    # --- Stats da bacia selecionada ---
    _ch_bacia = df_chamados_bacia.filter(pl.col("bacia") == sel_bacia.value) if df_chamados_bacia is not None else None
    _n_chamados = len(_ch_bacia) if _ch_bacia is not None else 0
    _dias_pos = set(_ch_bacia["dt_abertura"].dt.date().to_list()) if _ch_bacia is not None else set()
    _n_dias_pos = len(_dias_pos)

    # --- Confirmações por estação ---
    _conf_map = {}
    for _cod, _df_est in df_score.group_by("codEstacao"):
        _cod = _cod[0]
        _dias_est = set(_df_est["data"].to_list())
        _conf_map[_cod] = len(_dias_est & _dias_pos)

    # --- AUC + coordenadas ---
    _coords = (
        df_inventario
        .select(["codEstacao", "nomeEstacao", "latitude", "longitude", "primeira_leitura", "ultima_leitura"])
        .unique(subset=["codEstacao"])
    )
    _df_map = _coords.join(
        df_auc.filter(pl.col("bacia") == sel_bacia.value),
        on="codEstacao", how="left",
    )

    # --- Demérito por distância: score_ajustado = score × exp(-(d/d0)²) ---
    _d0_map = {
        "guarara": d0_guarara.value, "meninos": d0_meninos.value,
        "oratorio": d0_oratorio.value, "tamanduatei": d0_tamanduatei.value,
    }
    _d0 = _d0_map.get(sel_bacia.value, 8)
    _dist_km = [
        _haversine(r["latitude"], r["longitude"], _centroide_lat, _centroide_lon)
        for r in _df_map.iter_rows(named=True)
    ]
    _dist_factor = [_math.exp(-((d / _d0) ** 2)) for d in _dist_km]

    _scores_raw = [r["score"] if r["score"] is not None else None for r in _df_map.iter_rows(named=True)]
    _scores_adj_raw = [
        s * f if s is not None else None
        for s, f in zip(_scores_raw, _dist_factor)
    ]
    # Normalizar score_ajustado pelo máximo (excluindo None)
    _max_adj = max((v for v in _scores_adj_raw if v is not None), default=1.0)
    _scores_adj = [v / _max_adj if v is not None else None for v in _scores_adj_raw]

    _df_map = _df_map.with_columns([
        pl.Series("dist_km", _dist_km).round(2),
        pl.Series("score_ajustado", _scores_adj),
    ])

    _sem = _df_map.filter(pl.col("auc").is_null())
    _com = _df_map.filter(pl.col("auc").is_not_null())

    def _score_color(s):
        _t = (s or 0) ** 3
        _r = max(0, min(255, int(255 * (1 - _t))))
        _g = max(0, min(255, int(255 * _t)))
        return f"rgb({_r},{_g},0)"

    if len(_sem) > 0:
        _traces.append(go.Scattermapbox(
            lat=_sem["latitude"].to_list(), lon=_sem["longitude"].to_list(),
            mode="markers", marker=dict(size=10, color="#BDBDBD", opacity=0.5),
            text=[
                f"<b>{r['nomeEstacao']}</b><br>{r['codEstacao']}<br>"
                f"Dist. centróide: {r['dist_km']:.1f} km<br>Sem dados suficientes"
                for r in _sem.iter_rows(named=True)
            ],
            hoverinfo="text", name="Sem AUC",
        ))

    if len(_com) > 0:
        # Layer 1 — score original (círculo aberto, borda preta)
        _scores_orig = _com["score"].to_list()
        _sizes_orig = [10 + int(s * 22) for s in _scores_orig]
        _traces.append(go.Scattermapbox(
            lat=_com["latitude"].to_list(), lon=_com["longitude"].to_list(),
            mode="markers",
            marker=dict(size=_sizes_orig, color="rgba(0,0,0,0)", opacity=1.0,
                        allowoverlap=True),
            text=[f"<b>{r['nomeEstacao']}</b> — Score original: {r['score']:.3f}" for r in _com.iter_rows(named=True)],
            hoverinfo="text", name="Score original (anel)",
        ))

        # Layer 2 — score ajustado (círculo preenchido, cor verde/vermelho)
        _scores_adj_list = _com["score_ajustado"].to_list()
        _sizes_adj = [10 + int(s * 22) for s in _scores_adj_list]
        _colors_adj = [_score_color(s) for s in _scores_adj_list]
        _texts = []
        for r in _com.iter_rows(named=True):
            _conf = _conf_map.get(r["codEstacao"], 0)
            _pct = f"{_conf/_n_dias_pos*100:.1f}%" if _n_dias_pos > 0 else "—"
            _texts.append(
                f"<b>{r['nomeEstacao']}</b><br>{r['codEstacao']}<br>"
                f"{str(r['primeira_leitura'])[:10]} → {str(r['ultima_leitura'])[:10]}<br>"
                f"Dist. centróide: {r['dist_km']:.1f} km (d₀={_d0} km)<br>"
                f"Score original: {r['score']:.3f} → ajustado: {r['score_ajustado']:.3f}<br>"
                f"AUC: {r['auc']:.3f} · Cobertura: {r['cobertura']:.1%}<br>"
                f"Confirmações: {_conf} / {_n_dias_pos} dias ({_pct})"
            )
        _traces.append(go.Scattermapbox(
            lat=_com["latitude"].to_list(), lon=_com["longitude"].to_list(),
            mode="markers", marker=dict(size=_sizes_adj, color=_colors_adj, opacity=0.9),
            text=_texts, hoverinfo="text", name="Score ajustado (preenchido)",
        ))

    # Marcador do centróide da bacia
    _traces.append(go.Scattermapbox(
        lat=[_centroide_lat], lon=[_centroide_lon],
        mode="markers",
        marker=dict(size=12, color="black", symbol="circle"),
        text=[f"Centróide — {sel_bacia.value}"],
        hoverinfo="text", name="Centróide bacia",
    ))

    _fig = go.Figure(_traces)
    _fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_zoom=11,
        mapbox_center={"lat": _centroide_lat, "lon": _centroide_lon},
        height=580,
        title=f"Score por estação — bacia {sel_bacia.value} (d₀={_d0} km)",
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        dragmode="pan",
        legend=dict(bgcolor="rgba(255,255,255,0.85)", borderwidth=1),
    )
    mo.ui.plotly(_fig, config={"scrollZoom": True, "modeBarButtonsToRemove": ["select2d", "lasso2d"]})
    return


@app.cell
def _(
    d0_guarara,
    d0_meninos,
    d0_oratorio,
    d0_tamanduatei,
    df_auc,
    df_inventario,
    geojson_bacias,
    mo,
):
    import math as _math2

    def _haversine2(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = _math2.radians(lat2 - lat1)
        dlon = _math2.radians(lon2 - lon1)
        a = _math2.sin(dlat / 2) ** 2 + _math2.cos(_math2.radians(lat1)) * _math2.cos(_math2.radians(lat2)) * _math2.sin(dlon / 2) ** 2
        return R * 2 * _math2.asin(_math2.sqrt(a))

    def _centroide(bacia):
        _feats = [f for f in geojson_bacias["features"] if f["properties"]["MODELO"] == bacia]
        _lats, _lons = [], []
        for _feat in _feats:
            _geom = _feat["geometry"]
            _polys = _geom["coordinates"] if _geom["type"] == "MultiPolygon" else [_geom["coordinates"]]
            for _poly in _polys:
                for _ring in _poly:
                    for _coord in _ring:
                        _lons.append(_coord[0])
                        _lats.append(_coord[1])
        return (sum(_lats) / len(_lats), sum(_lons) / len(_lons)) if _lats else (-23.69, -46.52)

    # Coordenadas únicas por estação
    _coords = (
        df_inventario
        .select(["codEstacao", "municipio", "nomeEstacao", "latitude", "longitude"])
        .unique(subset=["codEstacao"])
    )
    _coords_dict = {r["codEstacao"]: r for r in _coords.iter_rows(named=True)}

    _d0_por_bacia = {
        "guarara": d0_guarara.value, "meninos": d0_meninos.value,
        "oratorio": d0_oratorio.value, "tamanduatei": d0_tamanduatei.value,
    }
    _rows_adj = []
    for _bacia_name, _df_b in df_auc.group_by("bacia"):
        _bacia_name = _bacia_name[0]
        _clat, _clon = _centroide(_bacia_name)
        # Normalizar score_ajustado pelo max da bacia
        _scores_adj_b = []
        _d0_b = _d0_por_bacia.get(_bacia_name, 8)
        for _r in _df_b.iter_rows(named=True):
            _coord = _coords_dict.get(_r["codEstacao"])
            if _coord:
                _d = _haversine2(_coord["latitude"], _coord["longitude"], _clat, _clon)
                _factor = _math2.exp(-((_d / _d0_b) ** 2))
            else:
                _d, _factor = 0.0, 1.0
            _scores_adj_b.append((_r["codEstacao"], _r["score"], _r["score"] * _factor, _d))
        _max_adj = max(s for _, _, s, _ in _scores_adj_b) or 1.0
        for _cod, _score, _sadj, _d in _scores_adj_b:
            _coord = _coords_dict.get(_cod, {})
            _rows_adj.append({
                "bacia": _bacia_name,
                "codEstacao": _cod,
                "municipio": _coord.get("municipio", ""),
                "nomeEstacao": _coord.get("nomeEstacao", ""),
                "score": _score,
                "dist_km": round(_d, 2),
                "score_ajustado": round(_sadj / _max_adj, 4),
            })

    import polars as _pl
    df_auc_ajustado = _pl.DataFrame(_rows_adj)
    mo.callout(
        mo.md(f"Score ajustado calculado para **{len(df_auc_ajustado)}** pares bacia × estação."),
        kind="success",
    )
    return (df_auc_ajustado,)


@app.cell
def _(mo):
    limiar_score = mo.ui.number(
        start=0.0, stop=1.0, step=0.05, value=0.3,
        label="Limiar mínimo de score ajustado",
    )
    mo.vstack([
        mo.md("## Seleção de estações por bacia"),
        mo.md("Estações com `score_ajustado ≥ limiar` serão incluídas no arquivo de configuração de cada bacia."),
        limiar_score,
    ])
    return (limiar_score,)


@app.cell
def _(df_auc_ajustado, limiar_score, mo):
    import json as _json2

    _limiar = limiar_score.value
    _df_sel = df_auc_ajustado.filter(df_auc_ajustado["score_ajustado"] >= _limiar)

    _linhas = []
    for _bacia_n in sorted(_df_sel["bacia"].unique().to_list()):
        _df_b = _df_sel.filter(_df_sel["bacia"] == _bacia_n)
        _por_mun = (
            _df_b.group_by("municipio").len().sort("municipio")
        )
        _partes = ", ".join(
            f"{r['municipio'].title()}: {r['len']}"
            for r in _por_mun.iter_rows(named=True)
        )
        _linhas.append(f"- **{_bacia_n}** ({len(_df_b)} estações) — {_partes}")

    btn_salvar = mo.ui.run_button(label="💾 Salvar estacoes_bacia.json")

    mo.vstack([
        mo.md("\n".join(_linhas)),
        btn_salvar,
    ])
    return (btn_salvar,)


@app.cell
def _(btn_salvar, df_auc_ajustado, limiar_score, mo):
    import json as _json3

    mo.stop(not btn_salvar.value)

    _df_save = df_auc_ajustado.filter(df_auc_ajustado["score_ajustado"] >= limiar_score.value)
    _out = {}
    for _b, _df_b2 in _df_save.group_by("bacia"):
        _b = _b[0]
        _out[_b] = sorted(_df_b2["codEstacao"].to_list())

    with open("dados/estacoes_bacia.json", "w", encoding="utf-8") as _f:
        _json3.dump(_out, _f, indent=2, ensure_ascii=False)

    _n_total = sum(len(v) for v in _out.values())
    mo.callout(
        mo.md(f"Salvo **dados/estacoes_bacia.json** — {_n_total} estações em {len(_out)} bacias."),
        kind="success",
    )
    return


if __name__ == "__main__":
    app.run()
