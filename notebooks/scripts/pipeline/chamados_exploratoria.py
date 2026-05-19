import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    import numpy as np
    import polars as pl
    import unicodedata
    import marimo as mo
    import altair as alt
    from datetime import datetime, timedelta

    return alt, datetime, json, mo, np, pl, timedelta, unicodedata


@app.cell
def _(unicodedata):
    def remover_acentos(texto: str) -> str:
        """Remove caracteres acentuados de uma string, substituindo-os por equivalentes ASCII."""
        return "".join(
            c
            for c in unicodedata.normalize("NFD", texto)
            if unicodedata.category(c) != "Mn"
        )

    return (remover_acentos,)


@app.cell
def _(pl):
    def converter_datahora(col_data: str, col_hora: str) -> pl.Expr:
        combinado = pl.col(col_data) + pl.lit(" ") + pl.col(col_hora)
        return combinado.str.strptime(
            pl.Datetime, "%Y/%m/%d %H:%M:%S", strict=False
        ).fill_null(
            combinado.str.strptime(pl.Datetime, "%Y/%m/%d %H:%M:%S%.3f", strict=False)
        )

    return (converter_datahora,)


@app.cell(hide_code=True)
def _():
    abbreviation_map = {
        'JARDIM': 'JD',
        'VILA': 'VL',
        'PARQUE': 'PQ',
        'CONJUNTO RESIDENCIAL': 'CJ RES',
        'CIDADE': 'CD',
        'SETOR': 'ST',
        'DISTRITO INDUSTRIAL': 'DIST IND',
        'NUCLEO HABITACIONAL': 'NUC HAB',
        'RESIDENCIAL': 'RES'
    }

    specific_corrections_map = {
        'VARZEA DO TAMANDUATE': 'VARZEA DO TAMANDUATEI',
        'VL FRANCISCO MATARAZ': 'VL FRANCISCO MATARAZZO',
        'PQ GERASSI CENTREVIL': 'PQ GERASSI',
        'JARDIM CLUBE DE CAMP': 'JD CLUBE DE CAMPO',
        'ESTANCIA DO RIO GRAN': 'ESTANCIA DO RIO GRANDE',
        'RECREIO DA BORDA DO': 'RECREIO DA BORDA DO CAMPO',
        'ACAMPAMENTO ANCHIETA': 'ACAMPAMENTO ANCHIETA',
        'ASS. ESPIRITO SANTO, 117': 'JD ESPIRITO SANTO',
        'BAIRRO INEXISTENTE': 'BAIRRO INEXISTENTE',
        'CAMPO GRANDE': 'CAMPO GRANDE',
        'JARDIM DO MIRANTE': 'JD DO MIRANTE',
        'JARDIM SANTO ANDRÉ': 'JD SANTO ANDRE',
        'PARANAPIACABA': 'PARANAPIACABA',
        'RIO GRANDE': 'RIO GRANDE',
        'SITIO TAQUARAL': 'SITIO TAQUARAL',
        'TAMANDUATEÍ 2': 'TAMANDUATEI 2',
        'TAMANDUATEÍ 3': 'TAMANDUATEI 3',
        'TAMANDUATEÍ 8': 'TAMANDUATEI 8',
        'VARZEA DO TAMANDUATEI': 'VARZEA DO TAMANDUATEI',
        'VILA JOÃO RAMALHO': 'VL JOAO RAMALHO',
        'VL FRANCISCO MATARAZZO': 'VL FRANCISCO MATARAZZO',
        'JD VILA RICA': 'JD VL RICA',
    }
    return abbreviation_map, specific_corrections_map


@app.cell(hide_code=True)
def _():
    ANO_INICIAL = 2016
    JANELAS_H = [1, 3, 6, 24, 48, 72]
    LOOKBACK_H = 72
    COD_ALAGAMENTO = "809"
    LIMIAR_DIAS_SUSPEITOS = 10
    return ANO_INICIAL, COD_ALAGAMENTO, JANELAS_H, LOOKBACK_H


@app.cell
def _(mo):
    mo.md(r"""
    # Chamados para a Defesa Civil
    """)
    return


@app.cell
def _(df_alagamentos, df_chamados_bacia, df_chamados_filtrado, mo, pl):
    _total = len(df_chamados_filtrado)
    _ano_min = int(df_chamados_filtrado["dt_abertura"].dt.year().min())
    _ano_max = int(df_chamados_filtrado["dt_abertura"].dt.year().max())
    _total_sem = int(df_chamados_bacia.filter(pl.col("bacia").is_null()).shape[0])
    _pct = (_total - _total_sem) / _total * 100 if _total > 0 else 0

    mo.hstack([
        mo.stat(value=f"{_ano_min}–{_ano_max}", label="Período", bordered=True),
        mo.stat(value=f"{_total:,}", label="Total de chamados", bordered=True),
        mo.stat(value=f"{_pct:.1f}%", label="Chamados na região metropolitana", bordered=True),
        mo.stat(value=f"{len(df_alagamentos):,}", label="Chamados de enchente", bordered=True),
    ], widths="equal")
    return


@app.cell
def _(pl, remover_acentos):
    df_chamados_bruto = (
        pl.read_csv("dados/chamados_raw.csv")
        .rename(lambda col: remover_acentos(col).lower().replace(" ", "_"))
        .select(
            [
                "data_abertura",
                "hora_abertura",
                "data_execucao",
                "hora_execucao",
                "servico_solicitado",
                "servico_executado",
                "endereco",
                "bairro",
                "longitude",
                "latitude",
                "observacao",
            ]
        )
    )
    return (df_chamados_bruto,)


@app.cell
def _(ANO_INICIAL, converter_datahora, df_chamados_bruto, pl):
    df_chamados_filtrado = (
        df_chamados_bruto
        .with_columns(
            converter_datahora("data_abertura", "hora_abertura").alias("dt_abertura"),
            converter_datahora("data_execucao", "hora_execucao").alias("dt_execucao"),
        )
        .drop("data_abertura", "hora_abertura", "data_execucao", "hora_execucao")
        .filter(pl.col("dt_abertura").dt.year() >= ANO_INICIAL)
    )
    return (df_chamados_filtrado,)


@app.cell
def _(
    abbreviation_map,
    df_chamados_filtrado,
    pl,
    remover_acentos,
    specific_corrections_map,
):
    def normalizar_bairro(nome: str) -> str:
        if nome is None:
            return None
        nome = remover_acentos(nome).upper().strip()
        if nome in specific_corrections_map:
            return specific_corrections_map[nome]
        for longo, curto in sorted(abbreviation_map.items(), key=lambda x: -len(x[0])):
            if nome.startswith(longo + " "):
                nome = curto + nome[len(longo):]
                break
        return nome

    df_chamados = df_chamados_filtrado.with_columns(
        pl.col("bairro").map_elements(normalizar_bairro, return_dtype=pl.Utf8).alias("bairro_norm")
    )
    return df_chamados, normalizar_bairro


@app.cell
def _(json, normalizar_bairro, pl):
    with open("dados/bacias.json") as f:
        _bacias_raw = json.load(f)

    _rows = []
    for bacia, bairros in _bacias_raw.items():
        for bairro in bairros:
            _rows.append({"bairro_bacia": normalizar_bairro(bairro), "bacia": bacia})

    df_bacias = pl.DataFrame(_rows).unique()
    return (df_bacias,)


@app.cell(hide_code=True)
def _(df_bacias, df_chamados):
    df_chamados_bacia = df_chamados.join(
        df_bacias,
        left_on="bairro_norm",
        right_on="bairro_bacia",
        how="left",
    )
    return (df_chamados_bacia,)


@app.cell
def _(COD_ALAGAMENTO, df_chamados_bacia, pl):
    df_alagamentos = df_chamados_bacia.filter(
        pl.col("servico_solicitado").str.starts_with(COD_ALAGAMENTO)
    )
    return (df_alagamentos,)


@app.cell(hide_code=True)
def _(mo):
    ano_ini = mo.ui.number(start=2016, stop=2025, step=1, value=2016)
    ano_fim = mo.ui.number(start=2016, stop=2025, step=1, value=2025)
    mo.md(f"""
    ## Sazonalidade — de {ano_ini} a {ano_fim}
    """)
    return ano_fim, ano_ini


@app.cell(hide_code=True)
def _(alt, ano_fim, ano_ini, df_alagamentos, pl):
    _meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
              "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

    _df_base = (
        df_alagamentos
        .drop_nulls("dt_abertura")
        .with_columns([
            pl.col("dt_abertura").dt.month().alias("mes"),
            pl.col("dt_abertura").dt.year().alias("ano"),
        ])
        .filter(
            (pl.col("ano") >= ano_ini.value) & (pl.col("ano") <= ano_fim.value)
        )
    )

    # Soma por mês (soma de todos os anos) — barras
    _df_total = (
        _df_base
        .group_by("mes")
        .agg(pl.len().alias("n_chamados"))
        .sort("mes")
        .with_columns(
            pl.col("mes").replace_strict({i + 1: m for i, m in enumerate(_meses)}, return_dtype=pl.String).alias("mes_nome")
        )
        .select(["mes_nome", "n_chamados"])
    )

    # Média por mês por ano — linha
    _df_media = (
        _df_base
        .group_by(["ano", "mes"])
        .agg(pl.len().alias("n_chamados"))
        .group_by("mes")
        .agg(pl.col("n_chamados").mean().alias("n_chamados"))
        .sort("mes")
        .with_columns(
            pl.col("mes").replace_strict({i + 1: m for i, m in enumerate(_meses)}, return_dtype=pl.String).alias("mes_nome")
        )
        .select(["mes_nome", "n_chamados"])
    )

    _df_barras = _df_total.with_columns(
        pl.col("n_chamados").cast(pl.Float64),
        pl.lit("Soma").alias("tipo"),
    )
    _df_linha = _df_media.with_columns(pl.lit("Média").alias("tipo"))

    _df_both = pl.concat([_df_barras, _df_linha])

    _color_scale = alt.Scale(
        domain=["Soma", "Média"],
        range=["#1f77b4", "#d62728"]
    )

    _base = alt.Chart(_df_both).encode(
        x=alt.X("mes_nome:N", title="Mês", sort=_meses),
        y=alt.Y("n_chamados:Q", title="# de chamados"),
        color=alt.Color("tipo:N", scale=_color_scale, legend=alt.Legend(title="Tipo", orient="bottom")),
        tooltip=[
            alt.Tooltip("mes_nome:N", title="Mês"),
            alt.Tooltip("n_chamados:Q", title="Chamados"),
        ],
    )

    (
        _base.transform_filter(alt.datum.tipo == "Soma").mark_bar()
        + _base.transform_filter(alt.datum.tipo == "Média").mark_line(point=True, size=3)
    ).properties(width="container", height=300)
    return


@app.cell
def _(mo):
    btn_cemaden = mo.ui.run_button(label="▶ Carregar dados CEMADEN")
    mo.md(f"## Pluviometria {btn_cemaden}")
    return (btn_cemaden,)


@app.cell
def _(btn_cemaden, mo, pl):
    mo.stop(
        not btn_cemaden.value,
        mo.callout(mo.md("Clique no botão acima para carregar os dados CEMADEN."), kind="warn"),
    )
    df_cemaden = (
        pl.read_parquet("dados/cemaden_abcd.parquet")
        .filter(pl.col("valor_mm").is_not_null() & (pl.col("valor_mm") >= 0))
    )
    mo.md(f"Carregados **{len(df_cemaden):,}** registros CEMADEN ({df_cemaden['municipio'].n_unique()} municípios).")
    return (df_cemaden,)


@app.cell
def _(mo):
    min_chamados = mo.ui.number(start=0, stop=50, step=1, value=3, label="Mínimo de chamados por dia de evento")
    mo.md(f"""
    ### Filtro de eventos por volume de chamados

    Dias com menos de **{min_chamados} chamados** 809.x são descartados das análises seguintes.
    Use para remover eventos isolados que podem ser falsos positivos ou registros incompletos.
    """)
    return (min_chamados,)


@app.cell
def _(df_cemaden, mo):
    mo.stop(
        df_cemaden is None,
        mo.callout(mo.md("Carregue o CEMADEN para continuar."), kind="warn"),
    )
    df_cemaden_filtrado = df_cemaden
    return (df_cemaden_filtrado,)


@app.cell
def _(df_cemaden_filtrado, pl):
    # Máximo horário entre todas as estações da cidade
    df_cemaden_horario = (
        df_cemaden_filtrado
        .with_columns(pl.col("dt").dt.truncate("1h").alias("hora"))
        .group_by("hora")
        .agg(pl.col("valor_mm").max().alias("chuva_max_mm"))
        .sort("hora")
    )
    return (df_cemaden_horario,)


@app.cell
def _(JANELAS_H, LOOKBACK_H, df_alagamentos, df_cemaden_horario, mo, pl):
    mo.stop(
        df_cemaden_horario is None,
        mo.callout(mo.md("Carregue o CEMADEN para calcular confirmações."), kind="warn"),
    )

    _chamados_idx = (
        df_alagamentos
        .drop_nulls("dt_abertura")
        .with_row_index("_idx")
        .with_columns([
            (pl.col("dt_abertura") - pl.duration(hours=LOOKBACK_H)).alias("dt_inicio"),
            pl.col("dt_abertura").alias("dt_fim"),
        ])
    )

    _joined = (
        _chamados_idx
        .join_where(
            df_cemaden_horario,
            pl.col("hora") >= pl.col("dt_inicio"),
            pl.col("hora") <= pl.col("dt_fim"),
        )
        .select(["_idx", "dt_fim", "hora", "chuva_max_mm"])
    )

    _accs = _chamados_idx.select("_idx")
    _joined_sorted = _joined.sort(["_idx", "hora"])
    for _h in JANELAS_H:
        _sub = (
            _joined_sorted
            .rolling("hora", period=f"{_h}h", group_by="_idx")
            .agg(pl.col("chuva_max_mm").sum().alias("rolling_acc"))
            .group_by("_idx")
            .agg(pl.col("rolling_acc").max().alias(f"acc_{_h}h"))
        )
        _accs = _accs.join(_sub, on="_idx", how="left")

    df_enchente_acc = (
        df_alagamentos
        .drop_nulls("dt_abertura")
        .with_row_index("_idx")
        .join(_accs, on="_idx", how="left")
        .drop("_idx")
    )
    return (df_enchente_acc,)


@app.cell
def _(df_enchente_acc, lims, pl):
    from functools import reduce as _reduce
    _janelas = list(lims.items())
    _cond = _reduce(
        lambda a, b: a | b,
        [pl.col(f"acc_{h}h").fill_null(0) >= lim for h, lim in _janelas],
    )
    df_enc_com_flag = df_enchente_acc.with_columns(_cond.alias("confirmado_chuva"))
    return (df_enc_com_flag,)


@app.cell
def _(df_enc_com_flag, min_chamados, pl):
    _dias_validos = (
        df_enc_com_flag
        .with_columns(pl.col("dt_abertura").dt.date().alias("_data"))
        .group_by("_data")
        .agg(pl.len().alias("_n"))
        .filter(pl.col("_n") >= min_chamados.value)
        .get_column("_data")
    )
    df_enchente_confirmado = (
        df_enc_com_flag
        .with_columns(pl.col("dt_abertura").dt.date().alias("_data"))
        .filter(pl.col("_data").is_in(_dias_validos))
        .drop("_data")
    )
    return (df_enchente_confirmado,)


@app.cell
def _(df_enchente_confirmado, mo, n_1h, n_24h, n_3h, n_48h, n_6h, n_72h):
    _janelas = [
        (1, n_1h.value), (3, n_3h.value), (6, n_6h.value),
        (24, n_24h.value), (48, n_48h.value), (72, n_72h.value),
    ]
    _total = len(df_enchente_confirmado)
    _cols  = " | ".join(f"**{h}h**" for h, _ in _janelas)
    _sep   = "|---" * (len(_janelas) + 1) + "|"
    _r_lim = " | ".join(str(lim) for _, lim in _janelas)
    _r_conf = " | ".join(
        f"{int((df_enchente_confirmado[f'acc_{h}h'].fill_null(0) >= lim).sum()):,} "
        f"({int((df_enchente_confirmado[f'acc_{h}h'].fill_null(0) >= lim).sum()) / _total * 100:.1f}%)"
        for h, lim in _janelas
    )
    tabela_confirmacoes = mo.md(f"""
    | | {_cols} |
    {_sep}
    | Limiar (mm) | {_r_lim} |
    | Confirmados | {_r_conf} |
    """)
    return (tabela_confirmacoes,)


@app.cell
def _(mo):
    n_1h  = mo.ui.number(start=1,  stop=150, step=1, value=20,  label="01h")
    n_3h  = mo.ui.number(start=5,  stop=200, step=1, value=30,  label="03h")
    n_6h  = mo.ui.number(start=5,  stop=300, step=1, value=45,  label="06h")
    n_24h = mo.ui.number(start=5,  stop=300, step=1, value=60,  label="24h")
    n_48h = mo.ui.number(start=5,  stop=300, step=1, value=80,  label="48h")
    n_72h = mo.ui.number(start=5,  stop=300, step=1, value=100, label="72h")
    return n_1h, n_24h, n_3h, n_48h, n_6h, n_72h


@app.cell
def _(n_1h, n_24h, n_3h, n_48h, n_6h, n_72h):
    lims = {
        1: n_1h.value, 3: n_3h.value, 6: n_6h.value,
        24: n_24h.value, 48: n_48h.value, 72: n_72h.value,
    }
    return (lims,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Confirmação de chamados por precipitação
    """)
    return


@app.cell
def _(mo, n_1h, n_24h, n_3h, n_48h, n_6h, n_72h, tabela_confirmacoes):
    mo.hstack([
        tabela_confirmacoes,
        mo.vstack([
            mo.md("**Limiares por janela temporal (mm)**"),
            mo.hstack([n_1h, n_3h, n_6h], widths="equal"),
            mo.hstack([n_24h, n_48h, n_72h], widths="equal"),
        ]),
    ], widths=[3, 2], gap="6", align="center")
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### Distribuição temporal por confirmação de chuva

    Use para calibrar os limiares: pontos **verdes** = algum chamado confirmado por chuva; pontos **vermelhos** = nenhum chamado confirmado.
    Clique num ponto para inspecionar o perfil de chuva das 72h anteriores.
    """)
    return


@app.cell
def _(alt, df_enchente_confirmado, mo, pl):
    _df_diario = (
        df_enchente_confirmado
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .group_by("data")
        .agg([
            pl.len().alias("n_chamados"),
            pl.col("confirmado_chuva").sum().alias("n_confirmados"),
        ])
        .sort("data")
        .with_columns(
            pl.when(pl.col("n_confirmados") > 0)
            .then(pl.lit("confirmado"))
            .otherwise(pl.lit("sem chuva"))
            .alias("status")
        )
    )

    _chart = (
        alt.Chart(_df_diario)
        .mark_circle(size=80, opacity=0.8)
        .encode(
            x=alt.X("data:T", title="Data", axis=alt.Axis(format="%Y", tickCount="year")),
            y=alt.Y("n_chamados:Q", title="Chamados no dia"),
            color=alt.Color(
                "status:N",
                scale=alt.Scale(
                    domain=["confirmado", "sem chuva"],
                    range=["#2ca02c", "#d62728"],
                ),
                legend=alt.Legend(title="Confirmação", orient="bottom"),
            ),
            tooltip=[
                alt.Tooltip("data:T", title="Data", format="%d/%m/%Y"),
                alt.Tooltip("n_chamados:Q", title="Chamados"),
                alt.Tooltip("n_confirmados:Q", title="Confirmados"),
            ],
        )
        .properties(width="container", height=280)
        .interactive()
    )

    chart_chamados = mo.ui.altair_chart(_chart)
    chart_chamados
    return (chart_chamados,)


@app.cell
def _(mo):
    threshold_seco = mo.ui.number(start=0.1, stop=30.0, step=0.1, value=0.5, label="Limiar hora seca (mm/h)")
    mo.md(f"""
    ### Eventos de chuva

    A janela do evento parte do pico (`dt_ajustado`) e expande para ambos os lados enquanto a chuva permanecer ≥ {threshold_seco} mm/h.
    """)
    return (threshold_seco,)


@app.cell
def _(
    alt,
    chart_chamados,
    datetime,
    df_cemaden_horario,
    df_enchente_eventos,
    mo,
    pl,
    timedelta,
):
    mo.stop(
        df_cemaden_horario is None,
        mo.callout(mo.md("Carregue o CEMADEN para ver o perfil de chuva."), kind="warn"),
    )

    _sel = chart_chamados.value
    mo.stop(
        len(_sel) == 0,
        mo.callout(
            mo.md("Clique num ponto do gráfico acima para ver o perfil de chuva."),
            kind="info",
        ),
    )

    _data = _sel["data"][0]

    # Todos os chamados do dia (confirmados e não confirmados)
    _df_all_chamados = (
        df_enchente_eventos
        .filter(pl.col("dt_abertura").dt.date() == _data)
        .select(["dt_abertura", "event_start", "event_end", "confirmado_chuva"])
    )
    _df_confirmed = _df_all_chamados.filter("confirmado_chuva")

    # Janela: 72h antes do chamado mais cedo, estendendo para cobrir event_start
    _dt_fim = datetime(_data.year, _data.month, _data.day) + timedelta(days=1)
    _earliest = _df_all_chamados["dt_abertura"].min()
    _dt_ini = _earliest - timedelta(hours=72)
    if len(_df_confirmed) > 0:
        _ev_start_min = _df_confirmed["event_start"].min()
        _dt_ini = min(_dt_ini, _ev_start_min)

    _df_janela = (
        df_cemaden_horario
        .filter((pl.col("hora") >= _dt_ini) & (pl.col("hora") < _dt_fim))
    )

    _dia_ref = _data.strftime("%d/%m/%Y")

    _line = (
        alt.Chart(_df_janela)
        .mark_line(color="#4e91d6", point=True)
        .encode(
            x=alt.X("hora:T", title="Hora"),
            y=alt.Y("chuva_max_mm:Q", title="mm/h"),
            tooltip=[
                alt.Tooltip("hora:T", title="Hora", format="%d/%m %H:%M"),
                alt.Tooltip("chuva_max_mm:Q", title="mm/h", format=".1f"),
            ],
        )
    )

    # <=4 chamados → riscos individuais; senão banda
    if len(_df_all_chamados) <= 4:
        _df_ch_uniq = (
            _df_all_chamados.select("dt_abertura").unique().rename({"dt_abertura": "hora"})
        )
        _chamados_marker = (
            alt.Chart(_df_ch_uniq)
            .mark_rule(color="gray", strokeWidth=1.5, strokeDash=[4, 4])
            .encode(x=alt.X("hora:T"))
        )
        _label_originais = "Originais (riscos)"
    else:
        _df_banda = pl.DataFrame({
            "x1": [_df_all_chamados["dt_abertura"].min()],
            "x2": [_df_all_chamados["dt_abertura"].max()],
        })
        _chamados_marker = (
            alt.Chart(_df_banda)
            .mark_rect(color="gray", opacity=0.2)
            .encode(x="x1:T", x2="x2:T")
        )
        _label_originais = "Originais (banda)"

    # Evento de chuva causador: banda se event_start != event_end, risco se ponto único (only_1h)
    if len(_df_confirmed) > 0:
        _df_ev = _df_confirmed.select(["event_start", "event_end"]).unique()
        _df_bands = _df_ev.filter(pl.col("event_start") != pl.col("event_end")).rename({"event_start": "x1", "event_end": "x2"})
        _df_rules = _df_ev.filter(pl.col("event_start") == pl.col("event_end")).rename({"event_start": "hora"}).select("hora")
    else:
        _df_bands = pl.DataFrame({"x1": pl.Series([], dtype=pl.Datetime), "x2": pl.Series([], dtype=pl.Datetime)})
        _df_rules = pl.DataFrame({"hora": pl.Series([], dtype=pl.Datetime)})

    _event_bands = (
        alt.layer(
            alt.Chart(_df_bands).mark_rect(color="#ff7f0e", opacity=0.25).encode(x="x1:T", x2="x2:T"),
            alt.Chart(_df_rules).mark_rule(color="#ff7f0e", strokeWidth=2).encode(x="hora:T"),
        )
    )

    # Legenda manual via pontos invisíveis
    _legend_types = [_label_originais] + (["Evento"] if len(_df_confirmed) > 0 else [])
    _legend_colors = ["gray"] + (["#ff7f0e"] if len(_df_confirmed) > 0 else [])
    _df_legend = pl.DataFrame({
        "hora": [_df_all_chamados["dt_abertura"].min()] * len(_legend_types),
        "mm": [0.0] * len(_legend_types),
        "tipo": _legend_types,
    })
    _legend = (
        alt.Chart(_df_legend)
        .mark_point(opacity=0)
        .encode(
            x=alt.X("hora:T"),
            y=alt.Y("mm:Q"),
            color=alt.Color("tipo:N", scale=alt.Scale(
                domain=_legend_types,
                range=_legend_colors,
            ), legend=alt.Legend(title="Horário")),
        )
    )

    (
        alt.layer(_line, _chamados_marker, _event_bands, _legend)
        .properties(
            width="container",
            height=280,
            title=f"Chuva máxima entre estações — 72h antes dos chamados de {_dia_ref}",
        )
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Ajustando horário/data dos chamados

    O chamado chega horas depois da chuva. Para ML, queremos o horário da chuva causadora.

    **`dt_ajustado`** — para cada chamado confirmado, buscamos nas 72h anteriores o pico de
    intensidade horária dentro da melhor janela acumulada (1h/3h/6h) que confirmou o evento,
    priorizando o candidato mais próximo ao `dt_abertura` original.

    **`event_start` / `event_end`** — expandimos o pico em ambas direções enquanto a chuva
    permanecer acima do limiar configurado (máx 6h por lado). Chamados confirmados só por 1h
    ficam como ponto único (`event_start = event_end`).
    """)
    return


@app.cell
def _(LOOKBACK_H, df_cemaden_horario, df_enchente_confirmado, lims, mo, pl):
    mo.stop(
        df_cemaden_horario is None,
        mo.callout(mo.md("Carregue o CEMADEN para ajustar horários."), kind="warn"),
    )

    # Índice estável sobre o df completo (sem nulls, como em df_enchente_acc)
    _df_idx = df_enchente_confirmado.with_row_index("_idx")

    # Subconjunto confirmado com janela de LOOKBACK_H
    _conf = (
        _df_idx
        .filter(pl.col("confirmado_chuva"))
        .with_columns([
            (pl.col("dt_abertura") - pl.duration(hours=LOOKBACK_H)).alias("dt_inicio"),
            pl.col("dt_abertura").alias("dt_fim"),
        ])
    )

    # Join com CEMADEN apenas para confirmados
    _joined = (
        _conf.select(["_idx", "dt_inicio", "dt_fim"])
        .join_where(
            df_cemaden_horario,
            pl.col("hora") >= pl.col("dt_inicio"),
            pl.col("hora") <= pl.col("dt_fim"),
        )
        .select(["_idx", "hora", "chuva_max_mm"])
    )

    # Para cada janela [1h, 3h, 6h], encontrar hora de pico 1h dentro da melhor janela
    _candidates = []
    _joined_sorted = _joined.sort(["_idx", "hora"])
    for _eff_w in [1, 3, 6]:
        # Fim da janela com maior acumulado
        _rolling_df = (
            _joined_sorted
            .rolling("hora", period=f"{_eff_w}h", group_by="_idx")
            .agg(pl.col("chuva_max_mm").sum().alias("rolling_acc"))
        )
        _best_end = (
            _rolling_df
            .group_by("_idx")
            .agg(
                pl.col("hora").sort_by("rolling_acc", descending=True).first().alias("window_end")
            )
        )
        # Pico 1h dentro de [window_end - eff_w h, window_end]
        _peak = (
            _joined_sorted
            .join(_best_end, on="_idx")
            .filter(
                (pl.col("hora") >= pl.col("window_end") - pl.duration(hours=_eff_w)) &
                (pl.col("hora") <= pl.col("window_end"))
            )
            .group_by("_idx")
            .agg(
                pl.col("hora").sort_by("chuva_max_mm", descending=True).first().alias("dt_candidato")
            )
            .with_columns(pl.lit(_eff_w).alias("eff_w"))
            .select(["_idx", "eff_w", "dt_candidato"])
        )
        _candidates.append(_peak)

    _all_cands = pl.concat(_candidates)

    # Associar acc values para filtrar por janela confirmadora
    _with_acc = _all_cands.join(
        _conf.select(["_idx", "dt_abertura", "acc_1h", "acc_3h", "acc_6h", "acc_24h", "acc_48h", "acc_72h"]),
        on="_idx",
    )

    # Manter apenas candidatos de janelas que confirmaram o chamado
    _valid = _with_acc.filter(
        ((pl.col("eff_w") == 1) & (pl.col("acc_1h").fill_null(0) >= lims[1])) |
        ((pl.col("eff_w") == 3) & (pl.col("acc_3h").fill_null(0) >= lims[3])) |
        ((pl.col("eff_w") == 6) & (
            (pl.col("acc_6h").fill_null(0) >= lims[6]) |
            (pl.col("acc_24h").fill_null(0) >= lims[24]) |
            (pl.col("acc_48h").fill_null(0) >= lims[48]) |
            (pl.col("acc_72h").fill_null(0) >= lims[72])
        ))
    )

    # Escolher candidato com menor deslocamento em relação ao dt_abertura original
    _best = (
        _valid
        .with_columns(
            (pl.col("dt_candidato") - pl.col("dt_abertura")).dt.total_seconds().abs().alias("displacement_s")
        )
        .group_by("_idx")
        .agg(
            pl.col("dt_candidato").sort_by("displacement_s").first().alias("dt_ajustado")
        )
    )

    # Merge de volta; não confirmados ficam com dt_abertura
    df_enchente_ajustado = (
        _df_idx
        .join(_best, on="_idx", how="left")
        .with_columns(
            pl.coalesce(["dt_ajustado", "dt_abertura"]).alias("dt_ajustado")
        )
        .drop("_idx")
    )
    return (df_enchente_ajustado,)


@app.cell
def _(alt, df_enchente_ajustado, pl):
    _df_desl = (
        df_enchente_ajustado
        .filter(pl.col("confirmado_chuva"))
        .with_columns(
            ((pl.col("dt_ajustado") - pl.col("dt_abertura")).dt.total_seconds() / 3600)
            .alias("deslocamento_h")
        )
        .select("deslocamento_h")
    )

    (
        alt.Chart(_df_desl)
        .mark_bar(color="#4e91d6")
        .encode(
            x=alt.X("deslocamento_h:Q", bin=alt.Bin(step=1), title="Deslocamento (horas)"),
            y=alt.Y("count()", title="# chamados"),
            tooltip=[
                alt.Tooltip("deslocamento_h:Q", bin=alt.Bin(step=1), title="Deslocamento (h)"),
                alt.Tooltip("count()", title="Chamados"),
            ],
        )
        .properties(width="container", height=250, title="Distribuição de deslocamentos de horário — chamados confirmados")
    )
    return


@app.cell
def _(
    df_cemaden_horario,
    df_enchente_ajustado,
    lims,
    mo,
    np,
    pl,
    threshold_seco,
):
    mo.stop(
        df_cemaden_horario is None,
        mo.callout(mo.md("Carregue o CEMADEN para segmentar eventos."), kind="warn"),
    )

    _threshold = threshold_seco.value
    _ONE_HOUR = np.timedelta64(65, "m")  # margem para gaps pequenos nos dados horários

    # Arrays numpy ordenados para busca eficiente
    _df_h = df_cemaden_horario.sort("hora")
    _hours_arr = _df_h["hora"].to_numpy()
    _chuva_arr = _df_h["chuva_max_mm"].to_numpy()

    _MAX_EACH_SIDE = np.timedelta64(6, "h")  # máx 6h por lado → janela total ≤ 12h

    def _find_bounds(peak_dt):
        """Expande a partir do pico em ambas direções enquanto chuva >= threshold, máx 6h por lado."""
        _peak = np.datetime64(peak_dt)
        _i = int(np.searchsorted(_hours_arr, _peak))
        _i = min(_i, len(_hours_arr) - 1)

        _left = _i
        while (
            _left > 0
            and (_hours_arr[_left] - _hours_arr[_left - 1]) <= _ONE_HOUR
            and _chuva_arr[_left - 1] >= _threshold
            and (_peak - _hours_arr[_left - 1]) <= _MAX_EACH_SIDE
        ):
            _left -= 1

        _right = _i
        while (
            _right < len(_hours_arr) - 1
            and (_hours_arr[_right + 1] - _hours_arr[_right]) <= _ONE_HOUR
            and _chuva_arr[_right + 1] >= _threshold
            and (_hours_arr[_right + 1] - _peak) <= _MAX_EACH_SIDE
        ):
            _right += 1

        return _hours_arr[_left].item(), _hours_arr[_right].item()

    # Condição: confirmado APENAS por 1h → mantém ponto único (sem event window)
    _only_1h = (
        (pl.col("acc_1h").fill_null(0) >= lims[1]) &
        (pl.col("acc_3h").fill_null(0) < lims[3]) &
        (pl.col("acc_6h").fill_null(0) < lims[6]) &
        (pl.col("acc_24h").fill_null(0) < lims[24]) &
        (pl.col("acc_48h").fill_null(0) < lims[48]) &
        (pl.col("acc_72h").fill_null(0) < lims[72])
    )

    # Para chamados confirmados por janela > 1h, expandir a partir do pico
    _df_idx = df_enchente_ajustado.with_row_index("_idx")
    _need_event = (
        _df_idx
        .filter(pl.col("confirmado_chuva") & ~_only_1h)
        .select(["_idx", "dt_ajustado"])
    )

    # Deduplica picos para não recomputar o mesmo horário várias vezes
    _unique_peaks = _need_event["dt_ajustado"].unique().to_list()
    _bounds_map = {_dt: _find_bounds(_dt) for _dt in _unique_peaks}

    _peaks_list = _need_event["dt_ajustado"].to_list()
    _matched = _need_event.with_columns([
        pl.Series("ev_start", [_bounds_map[_dt][0] for _dt in _peaks_list], dtype=pl.Datetime),
        pl.Series("ev_end",   [_bounds_map[_dt][1] for _dt in _peaks_list], dtype=pl.Datetime),
    ]).select(["_idx", "ev_start", "ev_end"])

    # Merge: only_1h ou não confirmado → event = ponto único em dt_ajustado
    df_enchente_eventos = (
        _df_idx
        .join(_matched, on="_idx", how="left")
        .with_columns([
            pl.coalesce(["ev_start", "dt_ajustado"]).alias("event_start"),
            pl.coalesce(["ev_end", "dt_ajustado"]).alias("event_end"),
        ])
        .drop(["_idx", "ev_start", "ev_end"])
    )
    return (df_enchente_eventos,)


@app.cell
def _(df_enchente_confirmado, mo, pl):
    _df_suspeitos = (
        df_enchente_confirmado
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .group_by("data")
        .agg([
            pl.len().alias("n_chamados"),
            pl.col("confirmado_chuva").any().alias("algum_confirmado"),
        ])
        .filter(~pl.col("algum_confirmado"))
        .sort("n_chamados", descending=True)
        .drop("algum_confirmado")
    )
    mo.vstack([
        mo.md(f"**{len(_df_suspeitos):,} dias com chamados 809.x sem confirmação de chuva em nenhuma estação**"),
        mo.callout(
            mo.md("Esses dias **não serão incluídos no export** de chamados confirmados."),
            kind="warn",
        ),
        mo.ui.table(_df_suspeitos),
    ])
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### Alagamentos confirmados sem chamados

    Eventos consolidados das 3 fontes externas que **não geraram chamados 809.x confirmados** numa janela de ±3 dias.
    Datas a menos de 3 dias entre si nas fontes são tratadas como o mesmo evento (mantém a mais antiga).
    """)
    return


@app.cell
def _(df_enchente_confirmado, mo, pl):
    from datetime import timedelta as _timedelta

    # --- Carregar e consolidar as 3 fontes externas ---
    _src1 = (
        pl.read_csv("dados/alagamentos_confirmados.csv")
        .with_columns(pl.col("dt").str.to_date())
        .select(pl.col("dt").alias("data"), pl.lit("alagamentos_confirmados").alias("fonte"))
    )
    _src2 = (
        pl.read_csv("dados/fonte_gpt.csv")
        .filter(pl.col("Check") == "TRUE")
        .with_columns(pl.col("Data").str.to_date("%d/%m/%Y").alias("data"))
        .select("data", pl.lit("fonte_gpt").alias("fonte"))
    )
    _src3 = (
        pl.read_csv("dados/maior_tres_verificado_gpt.csv")
        .with_columns(pl.col("Data").str.to_date("%d/%m/%Y").alias("data"))
        .select("data", pl.lit("maior_tres").alias("fonte"))
    )

    _todas = pl.concat([_src1, _src2, _src3]).sort("data")

    # Deduplicar com tolerância de 3 dias: percorre em ordem, agrupa datas próximas
    _datas_sorted = _todas["data"].unique().sort().to_list()
    _deduped = []
    _last = None
    for _d in _datas_sorted:
        if _last is None or (_d - _last).days > 3:
            _deduped.append(_d)
            _last = _d

    # Fontes de cada data deduplicada (qual(is) fontes contribuíram para o cluster)
    _rep = []
    for _d_rep in _deduped:
        _fontes = (
            _todas
            .filter(
                (pl.col("data") >= pl.lit(_d_rep) - pl.duration(days=3)) &
                (pl.col("data") <= pl.lit(_d_rep) + pl.duration(days=3))
            )
            ["fonte"].unique().sort().to_list()
        )
        _rep.append({"dt": _d_rep, "fontes": ", ".join(_fontes)})

    _df_conf_ext = pl.DataFrame(_rep).with_columns(pl.col("dt").cast(pl.Date))

    # --- Cruzar com chamados confirmados (±3 dias) ---
    _chamados_datas = (
        df_enchente_confirmado
        .filter(pl.col("confirmado_chuva"))
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .select("data")
        .unique()
    )

    _df_conf_with_window = _df_conf_ext.with_columns([
        (pl.col("dt") - pl.duration(days=3)).alias("dt_ini"),
        (pl.col("dt") + pl.duration(days=3)).alias("dt_fim"),
    ])
    _has_chamado = (
        _df_conf_with_window
        .join_where(
            _chamados_datas.rename({"data": "data_ch"}),
            pl.col("data_ch") >= pl.col("dt_ini"),
            pl.col("data_ch") <= pl.col("dt_fim"),
        )
        .select("dt")
        .unique()
    )

    _df_sem = (
        _df_conf_ext
        .join(_has_chamado, on="dt", how="anti")
        .sort("dt")
    )

    _n_total_ext = len(_df_conf_ext)
    _n_com_chamado = _n_total_ext - len(_df_sem)

    _opcoes = {d.strftime("%d/%m/%Y"): d for d in _df_sem["dt"].to_list()}

    seletor_conf_sem_chamados = mo.ui.dropdown(
        options=_opcoes,
        label="Selecionar evento para ver perfil de chuva",
    )

    mo.vstack([
        mo.hstack([
            mo.stat(value=str(_n_total_ext), label="Eventos externos únicos", bordered=True),
            mo.stat(value=str(_n_com_chamado), label="Cobertos por chamados", bordered=True),
            mo.stat(value=str(len(_df_sem)), label="Sem chamados — para revisar", bordered=True),
        ], widths="equal"),
        mo.md("**Eventos sem chamados 809.x confirmados em ±3 dias:**"),
        mo.ui.table(_df_sem),
        mo.callout(
            mo.md("**TODO:** Para cada evento desta lista, buscar notícias de enchente e decidir se entra na lista consolidada de datas confirmadas."),
            kind="info",
        ),
        seletor_conf_sem_chamados,
    ])
    return (seletor_conf_sem_chamados,)


@app.cell
def _(
    alt,
    datetime,
    df_cemaden_horario,
    lims,
    mo,
    np,
    pl,
    seletor_conf_sem_chamados,
    threshold_seco,
    timedelta,
):
    mo.stop(
        df_cemaden_horario is None,
        mo.callout(mo.md("Carregue o CEMADEN para ver o perfil de chuva."), kind="warn"),
    )
    mo.stop(
        seletor_conf_sem_chamados.value is None,
        mo.callout(mo.md("Selecione um evento acima."), kind="info"),
    )

    _data_ev = seletor_conf_sem_chamados.value

    _dt_fim = datetime(_data_ev.year, _data_ev.month, _data_ev.day) + timedelta(days=1)
    _dt_ini = _dt_fim - timedelta(hours=72)

    _df_janela_ev = (
        df_cemaden_horario
        .filter((pl.col("hora") >= _dt_ini) & (pl.col("hora") < _dt_fim))
        .sort("hora")
    )

    mo.stop(
        len(_df_janela_ev) == 0,
        mo.callout(mo.md("Sem dados CEMADEN para este período."), kind="warn"),
    )

    # Acumulados máximos por janela — mesma lógica do chamados
    _accs = {}
    for _h in [1, 3, 6, 24, 48, 72]:
        _acc = (
            _df_janela_ev
            .rolling("hora", period=f"{_h}h")
            .agg(pl.col("chuva_max_mm").sum())
            ["chuva_max_mm"].max()
        )
        _accs[_h] = _acc or 0.0

    # Janelas que confirmam o evento
    _confirmed_wins = [_h for _h in [1, 3, 6, 24, 48, 72] if _accs[_h] >= lims[_h]]

    _dia_ref_ev = _data_ev.strftime("%d/%m/%Y")

    _line_ev = (
        alt.Chart(_df_janela_ev)
        .mark_line(color="#4e91d6", point=True)
        .encode(
            x=alt.X("hora:T", title="Hora"),
            y=alt.Y("chuva_max_mm:Q", title="mm/h"),
            tooltip=[
                alt.Tooltip("hora:T", title="Hora", format="%d/%m %H:%M"),
                alt.Tooltip("chuva_max_mm:Q", title="mm/h", format=".1f"),
            ],
        )
    )

    if not _confirmed_wins:
        _chart_ev = _line_ev
    else:
        # eff_w: menor janela confirmadora, cap em 6h (janelas maiores usam eff_w=6 para o pico)
        _eff_w = min(min(_confirmed_wins), 6)
        _only_1h = _confirmed_wins == [1]

        # Fim da melhor janela acumulada → pico de 1h dentro dela
        _rolling_best = (
            _df_janela_ev
            .rolling("hora", period=f"{_eff_w}h")
            .agg(pl.col("chuva_max_mm").sum().alias("rolling_acc"))
        )
        _window_end = (
            _rolling_best.sort("rolling_acc", descending=True).row(0, named=True)["hora"]
        )
        _peak_dt_ev = (
            _df_janela_ev
            .filter(
                (pl.col("hora") >= _window_end - pl.duration(hours=_eff_w)) &
                (pl.col("hora") <= _window_end)
            )
            .sort("chuva_max_mm", descending=True)
            .row(0, named=True)["hora"]
        )

        # Expandir do pico — idêntico à lógica de chamados
        _df_h_ev = df_cemaden_horario.sort("hora")
        _hours_arr_ev = _df_h_ev["hora"].to_numpy()
        _chuva_arr_ev = _df_h_ev["chuva_max_mm"].to_numpy()
        _threshold_ev = threshold_seco.value
        _ONE_HOUR_EV = np.timedelta64(65, "m")
        _MAX_EACH_SIDE_EV = np.timedelta64(6, "h")

        def _find_bounds_ev(peak_dt):
            _peak = np.datetime64(peak_dt)
            _i = min(int(np.searchsorted(_hours_arr_ev, _peak)), len(_hours_arr_ev) - 1)
            _left = _i
            while (
                _left > 0
                and (_hours_arr_ev[_left] - _hours_arr_ev[_left - 1]) <= _ONE_HOUR_EV
                and _chuva_arr_ev[_left - 1] >= _threshold_ev
                and (_peak - _hours_arr_ev[_left - 1]) <= _MAX_EACH_SIDE_EV
            ):
                _left -= 1
            _right = _i
            while (
                _right < len(_hours_arr_ev) - 1
                and (_hours_arr_ev[_right + 1] - _hours_arr_ev[_right]) <= _ONE_HOUR_EV
                and _chuva_arr_ev[_right + 1] >= _threshold_ev
                and (_hours_arr_ev[_right + 1] - _peak) <= _MAX_EACH_SIDE_EV
            ):
                _right += 1
            return _hours_arr_ev[_left].item(), _hours_arr_ev[_right].item()

        if _only_1h:
            _ev_start, _ev_end = _peak_dt_ev, _peak_dt_ev
        else:
            _ev_start, _ev_end = _find_bounds_ev(_peak_dt_ev)

        if _ev_start != _ev_end:
            _df_ev_band = pl.DataFrame({"x1": [_ev_start], "x2": [_ev_end]})
            _event_layer_ev = (
                alt.Chart(_df_ev_band)
                .mark_rect(color="#ff7f0e", opacity=0.25)
                .encode(x="x1:T", x2="x2:T")
            )
        else:
            _df_ev_rule = pl.DataFrame({"hora": pl.Series([_ev_start], dtype=pl.Datetime)})
            _event_layer_ev = (
                alt.Chart(_df_ev_rule)
                .mark_rule(color="#ff7f0e", strokeWidth=2)
                .encode(x="hora:T")
            )

        _df_legend_ev = pl.DataFrame({
            "hora": pl.Series([_peak_dt_ev], dtype=pl.Datetime),
            "mm": [0.0],
            "tipo": ["Evento"],
        })
        _legend_ev = (
            alt.Chart(_df_legend_ev)
            .mark_point(opacity=0)
            .encode(
                x=alt.X("hora:T"),
                y=alt.Y("mm:Q"),
                color=alt.Color(
                    "tipo:N",
                    scale=alt.Scale(domain=["Evento"], range=["#ff7f0e"]),
                    legend=alt.Legend(title=""),
                ),
            )
        )

        _chart_ev = alt.layer(_line_ev, _event_layer_ev, _legend_ev)

    _chart_ev.properties(
        width="container",
        height=280,
        title=f"Chuva máxima entre estações — 72h antes de {_dia_ref_ev} (sem chamados registrados)",
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### Sinal de chuva sem registro de enchente

    Dias onde o CEMADEN mostra padrão de risco (alguma janela >= limiar) mas **não há chamados 809.x
    nem eventos confirmados** em ±3 dias. Possíveis causas: falha de registro, área não coberta pelos
    chamados, evento real que não gerou demanda à prefeitura.
    """)
    return


@app.cell
def _(mo):
    sel_anos = mo.ui.range_slider(
        start=2016, stop=2025, step=1,
        value=[2016, 2025],
        label="Período (anos)",
        show_value=True,
    )
    sel_anos
    return (sel_anos,)


@app.cell
def _(df_cemaden_horario, df_enchente_confirmado, lims, mo, pl, sel_anos):
    mo.stop(
        df_cemaden_horario is None,
        mo.callout(mo.md("Carregue o CEMADEN para esta análise."), kind="warn"),
    )

    _ano_ini, _ano_fim = sel_anos.value

    # Acumulado máximo por janela para cada hora do histórico (filtrado por período)
    _df_sorted = (
        df_cemaden_horario
        .filter(
            (pl.col("hora").dt.year() >= _ano_ini) &
            (pl.col("hora").dt.year() <= _ano_fim)
        )
        .sort("hora")
    )
    _frames = [_df_sorted.select("hora")]
    for _h in [1, 3, 6, 24, 48, 72]:
        _frames.append(
            _df_sorted
            .rolling("hora", period=f"{_h}h")
            .agg(pl.col("chuva_max_mm").sum().alias(f"acc_{_h}h"))
            .select(f"acc_{_h}h")
        )
    _df_accs = pl.concat(_frames, how="horizontal")

    # Dias onde alguma janela atinge o limiar
    _df_rainy = (
        _df_accs
        .filter(
            (pl.col("acc_1h") >= lims[1]) |
            (pl.col("acc_3h") >= lims[3]) |
            (pl.col("acc_6h") >= lims[6]) |
            (pl.col("acc_24h") >= lims[24]) |
            (pl.col("acc_48h") >= lims[48]) |
            (pl.col("acc_72h") >= lims[72])
        )
        .with_columns(pl.col("hora").dt.date().alias("data"))
        .group_by("data")
        .agg([
            pl.col("acc_1h").max(),
            pl.col("acc_3h").max(),
            pl.col("acc_6h").max(),
            pl.col("acc_24h").max(),
            pl.col("acc_48h").max(),
            pl.col("acc_72h").max(),
        ])
        .sort("data")
    )

    # Datas com chamados em ±3 dias
    _chamados_datas = (
        df_enchente_confirmado
        .with_columns(pl.col("dt_abertura").dt.date().alias("data_ch"))
        .select("data_ch").unique()
    )
    _has_chamado = (
        _df_rainy
        .with_columns([
            (pl.col("data") - pl.duration(days=3)).alias("ini"),
            (pl.col("data") + pl.duration(days=3)).alias("fim"),
        ])
        .join_where(
            _chamados_datas,
            pl.col("data_ch") >= pl.col("ini"),
            pl.col("data_ch") <= pl.col("fim"),
        )
        .select("data").unique()
    )

    # Datas com evento confirmado em ±3 dias
    _conf_ext = (
        pl.read_csv("dados/alagamentos_confirmados.csv")
        .with_columns(pl.col("dt").str.to_date().alias("data_conf"))
        .select("data_conf")
    )
    _has_confirmed = (
        _df_rainy
        .with_columns([
            (pl.col("data") - pl.duration(days=3)).alias("ini"),
            (pl.col("data") + pl.duration(days=3)).alias("fim"),
        ])
        .join_where(
            _conf_ext,
            pl.col("data_conf") >= pl.col("ini"),
            pl.col("data_conf") <= pl.col("fim"),
        )
        .select("data").unique()
    )

    _df_candidatos = (
        _df_rainy
        .join(_has_chamado, on="data", how="anti")
        .join(_has_confirmed, on="data", how="anti")
        .sort("data")
    )

    # Conjunto de todos os dias confirmados (chamados + fontes externas)
    _datas_conf_set = set(
        pl.concat([
            df_enchente_confirmado
                .filter(pl.col("confirmado_chuva"))
                .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
                .select("data"),
            pl.read_csv("dados/alagamentos_confirmados.csv")
                .with_columns(pl.col("dt").str.to_date().alias("data"))
                .select("data"),
        ]).unique()["data"].to_list()
    )

    # Deduplicação greedy: manter só o primeiro de cada cluster de 3 dias,
    # também excluindo dias próximos a eventos confirmados
    _kept = []
    _last = None
    for _row in _df_candidatos["data"].to_list():
        if _last is not None and (_row - _last).days <= 3:
            continue
        if any(abs((_row - _d).days) <= 3 for _d in _datas_conf_set):
            continue
        _kept.append(_row)
        _last = _row

    df_sinal_sem_registro = _df_candidatos.filter(pl.col("data").is_in(_kept))

    _n_rainy = len(_df_rainy)
    _n_com_registro = _n_rainy - len(_df_candidatos)
    _n_ambiguos = len(_df_candidatos)
    _n_dedup = len(df_sinal_sem_registro)

    _funil = mo.callout(mo.md(
        f"**{_n_rainy}** dias chuvosos ({_ano_ini}–{_ano_fim}) → "
        f"**{_n_com_registro}** com chamado/confirmado → "
        f"**{_n_ambiguos}** sem registro → "
        f"**{_n_dedup}** após deduplicação (±3 dias)"
    ), kind="warn")

    _stat = mo.stat(
        value=str(_n_dedup),
        label="Dias para analisar",
        caption="sinal de chuva sem registro de enchente",
    )

    _acc_cols = [c for c in df_sinal_sem_registro.columns if c.startswith("acc_")]
    _tabela_df = df_sinal_sem_registro.with_columns(
        [pl.col(c).round(1) for c in _acc_cols]
    )

    tabela_sinal_sem_registro = mo.ui.table(
        _tabela_df,
        selection="single",
        label="Dias com sinal de risco sem registro de enchente",
    )
    mo.vstack([mo.hstack([_stat, _funil], align="center"), tabela_sinal_sem_registro])
    return df_sinal_sem_registro, tabela_sinal_sem_registro


@app.cell
def _(
    alt,
    datetime,
    df_cemaden_horario,
    lims,
    mo,
    np,
    pl,
    tabela_sinal_sem_registro,
    threshold_seco,
    timedelta,
):
    mo.stop(
        df_cemaden_horario is None,
        mo.callout(mo.md("Carregue o CEMADEN para ver o perfil de chuva."), kind="warn"),
    )
    mo.stop(
        len(tabela_sinal_sem_registro.value) == 0,
        mo.callout(mo.md("Selecione uma linha da tabela acima."), kind="info"),
    )

    _data_sr = tabela_sinal_sem_registro.value["data"][0]

    _dt_fim_sr = datetime(_data_sr.year, _data_sr.month, _data_sr.day) + timedelta(days=1)
    _dt_ini_sr = _dt_fim_sr - timedelta(hours=72)

    _df_janela_sr = (
        df_cemaden_horario
        .filter((pl.col("hora") >= _dt_ini_sr) & (pl.col("hora") < _dt_fim_sr))
        .sort("hora")
    )

    # Janela confirmadora (sempre existe — dia foi filtrado por isso)
    _accs_sr = {}
    for _h_sr in [1, 3, 6, 24, 48, 72]:
        _v = (
            _df_janela_sr
            .rolling("hora", period=f"{_h_sr}h")
            .agg(pl.col("chuva_max_mm").sum())
            ["chuva_max_mm"].max()
        )
        _accs_sr[_h_sr] = _v or 0.0

    _confirmed_sr = [_h for _h in [1, 3, 6, 24, 48, 72] if _accs_sr[_h] >= lims[_h]]
    _eff_w_sr = min(min(_confirmed_sr), 6)
    _only_1h_sr = _confirmed_sr == [1]

    _rolling_sr = (
        _df_janela_sr
        .rolling("hora", period=f"{_eff_w_sr}h")
        .agg(pl.col("chuva_max_mm").sum().alias("rolling_acc"))
    )
    _window_end_sr = _rolling_sr.sort("rolling_acc", descending=True).row(0, named=True)["hora"]
    _peak_dt_sr = (
        _df_janela_sr
        .filter(
            (pl.col("hora") >= _window_end_sr - pl.duration(hours=_eff_w_sr)) &
            (pl.col("hora") <= _window_end_sr)
        )
        .sort("chuva_max_mm", descending=True)
        .row(0, named=True)["hora"]
    )

    _df_h_sr = df_cemaden_horario.sort("hora")
    _hours_sr = _df_h_sr["hora"].to_numpy()
    _chuva_sr = _df_h_sr["chuva_max_mm"].to_numpy()
    _thr_sr = threshold_seco.value
    _ONE_H_SR = np.timedelta64(65, "m")
    _MAX_SIDE_SR = np.timedelta64(6, "h")

    def _find_bounds_sr(peak_dt):
        _peak = np.datetime64(peak_dt)
        _i = min(int(np.searchsorted(_hours_sr, _peak)), len(_hours_sr) - 1)
        _l = _i
        while (
            _l > 0
            and (_hours_sr[_l] - _hours_sr[_l - 1]) <= _ONE_H_SR
            and _chuva_sr[_l - 1] >= _thr_sr
            and (_peak - _hours_sr[_l - 1]) <= _MAX_SIDE_SR
        ):
            _l -= 1
        _r = _i
        while (
            _r < len(_hours_sr) - 1
            and (_hours_sr[_r + 1] - _hours_sr[_r]) <= _ONE_H_SR
            and _chuva_sr[_r + 1] >= _thr_sr
            and (_hours_sr[_r + 1] - _peak) <= _MAX_SIDE_SR
        ):
            _r += 1
        return _hours_sr[_l].item(), _hours_sr[_r].item()

    _ev_start_sr, _ev_end_sr = (_peak_dt_sr, _peak_dt_sr) if _only_1h_sr else _find_bounds_sr(_peak_dt_sr)

    _dia_ref_sr = _data_sr.strftime("%d/%m/%Y")

    _line_sr = (
        alt.Chart(_df_janela_sr)
        .mark_line(color="#4e91d6", point=True)
        .encode(
            x=alt.X("hora:T", title="Hora"),
            y=alt.Y("chuva_max_mm:Q", title="mm/h"),
            tooltip=[
                alt.Tooltip("hora:T", title="Hora", format="%d/%m %H:%M"),
                alt.Tooltip("chuva_max_mm:Q", title="mm/h", format=".1f"),
            ],
        )
    )

    if _ev_start_sr != _ev_end_sr:
        _df_band_sr = pl.DataFrame({"x1": [_ev_start_sr], "x2": [_ev_end_sr]})
        _event_sr = alt.Chart(_df_band_sr).mark_rect(color="#ff7f0e", opacity=0.25).encode(x="x1:T", x2="x2:T")
    else:
        _df_rule_sr = pl.DataFrame({"hora": pl.Series([_ev_start_sr], dtype=pl.Datetime)})
        _event_sr = alt.Chart(_df_rule_sr).mark_rule(color="#ff7f0e", strokeWidth=2).encode(x="hora:T")

    _df_leg_sr = pl.DataFrame({
        "hora": pl.Series([_peak_dt_sr], dtype=pl.Datetime),
        "mm": [0.0],
        "tipo": ["Evento"],
    })
    _legend_sr = (
        alt.Chart(_df_leg_sr)
        .mark_point(opacity=0)
        .encode(
            x=alt.X("hora:T"),
            y=alt.Y("mm:Q"),
            color=alt.Color(
                "tipo:N",
                scale=alt.Scale(domain=["Evento"], range=["#ff7f0e"]),
                legend=alt.Legend(title=""),
            ),
        )
    )

    (
        alt.layer(_line_sr, _event_sr, _legend_sr)
        .properties(
            width="container",
            height=280,
            title=f"Chuva máxima entre estações — 72h antes de {_dia_ref_sr} (sem registro de enchente)",
        )
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Diagnóstico: dias com chuva sem registro de enchente

    Comparação entre três categorias de dias. **Confirmados**: chamados 809.x validados por chuva
    ou constam nas fontes externas. **Ambíguos**: alguma janela ≥ limiar, mas sem chamados nem
    confirmação externa em ±3 dias. **Negativos**: nenhum critério de chuva atendido.

    Ajuste os limiares na seção anterior para ver como as categorias se redistribuem.
    """)
    return


@app.cell
def _(mo):
    sel_janela = mo.ui.radio(
        options={"1h": 1, "3h": 3, "6h": 6, "24h": 24, "48h": 48, "72h": 72},
        value="6h",
        label="Janela de acumulado",
        inline=True,
    )
    sel_janela
    return (sel_janela,)


@app.cell
def _(
    alt,
    df_cemaden_horario,
    df_enchente_confirmado,
    df_sinal_sem_registro,
    lims,
    mo,
    pl,
    sel_anos,
    sel_janela,
):
    mo.stop(
        df_cemaden_horario is None,
        mo.callout(mo.md("Carregue o CEMADEN para esta análise."), kind="warn"),
    )

    _ano_ini, _ano_fim = sel_anos.value

    # Acumulado rolling da janela selecionada, máximo por dia
    _h = sel_janela.value
    _df_diario = (
        df_cemaden_horario
        .filter(
            (pl.col("hora").dt.year() >= _ano_ini) &
            (pl.col("hora").dt.year() <= _ano_fim)
        )
        .sort("hora")
        .rolling("hora", period=f"{_h}h")
        .agg(pl.col("chuva_max_mm").sum().alias("acc"))
        .with_columns(pl.col("hora").dt.date().alias("data"))
        .group_by("data")
        .agg(pl.col("acc").max().alias("precip_janela"))
        .sort("data")
    )

    # Datas confirmadas: chamados + fontes externas
    _datas_conf_chamado = (
        df_enchente_confirmado
        .filter(pl.col("confirmado_chuva"))
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .select("data").unique()
    )
    _datas_conf_ext = (
        pl.read_csv("dados/alagamentos_confirmados.csv")
        .with_columns(pl.col("dt").str.to_date().alias("data"))
        .select("data")
    )
    _datas_conf = pl.concat([_datas_conf_chamado, _datas_conf_ext]).unique()

    # Atribuição de categoria por dia (df_sinal_sem_registro já filtrado por período)
    _df_cat = (
        _df_diario
        .join(_datas_conf.with_columns(pl.lit(True).alias("_conf")), on="data", how="left")
        .join(
            df_sinal_sem_registro.select("data").with_columns(pl.lit(True).alias("_ambig")),
            on="data", how="left",
        )
        .with_columns(
            pl.when(pl.col("_conf"))
              .then(pl.lit("Confirmado"))
              .when(pl.col("_ambig"))
              .then(pl.lit("Ambíguo"))
              .otherwise(pl.lit("Negativo"))
              .alias("categoria")
        )
        .drop(["_conf", "_ambig"])
    )

    _cor_scale = alt.Scale(
        domain=["Confirmado", "Ambíguo", "Negativo"],
        range=["#e07b39", "#888888", "#9ecae1"],
    )
    _titulo_eixo = f"Acumulado {_h}h (mm)"

    # Gráfico 1 — box plot: distribuição de precipitação por categoria
    _df_vis = _df_cat.filter(pl.col("precip_janela") > 0)
    _box = (
        alt.Chart(_df_vis)
        .mark_boxplot(extent="min-max", size=40)
        .encode(
            x=alt.X("categoria:N", title=None, sort=["Confirmado", "Ambíguo", "Negativo"]),
            y=alt.Y("precip_janela:Q", title=_titulo_eixo),
            color=alt.Color("categoria:N", scale=_cor_scale, legend=None),
        )
        .properties(width="container", height=220, title="Os dias ambíguos têm chuva parecida com os confirmados?")
    )

    # Gráfico 2 — ECDF da precipitação por categoria
    _ecdf = (
        alt.Chart(_df_vis)
        .transform_window(
            ecdf="cume_dist()",
            sort=[{"field": "precip_janela"}],
            groupby=["categoria"],
        )
        .mark_line(interpolate="step-after", strokeWidth=2)
        .encode(
            x=alt.X("precip_janela:Q", title=_titulo_eixo),
            y=alt.Y("ecdf:Q", title="% acumulado", axis=alt.Axis(format="%", labelAngle=0)),
            color=alt.Color("categoria:N", scale=_cor_scale, legend=alt.Legend(title="Categoria")),
            order=alt.Order("precip_janela:Q"),
        )
        .properties(width="container", height=200, title="Distribuição acumulada por categoria")
    )

    # Gráfico 3 — quantos critérios cada dia ambíguo atende
    _df_crit = (
        df_sinal_sem_registro
        .with_columns(
            (
                (pl.col("acc_1h")  >= lims[1]).cast(pl.Int32) +
                (pl.col("acc_3h")  >= lims[3]).cast(pl.Int32) +
                (pl.col("acc_6h")  >= lims[6]).cast(pl.Int32) +
                (pl.col("acc_24h") >= lims[24]).cast(pl.Int32) +
                (pl.col("acc_48h") >= lims[48]).cast(pl.Int32) +
                (pl.col("acc_72h") >= lims[72]).cast(pl.Int32)
            ).alias("criteria_count")
        )
        .group_by("criteria_count")
        .agg(pl.len().alias("n_dias"))
        .sort("criteria_count")
    )
    _bar = (
        alt.Chart(_df_crit)
        .mark_bar(color="#888888")
        .encode(
            x=alt.X("criteria_count:O", title="Critérios atendidos"),
            y=alt.Y("n_dias:Q", title="Dias ambíguos"),
            tooltip=["criteria_count:O", "n_dias:Q"],
        )
        .properties(width="container", height=180, title="Dias ambíguos: quantos critérios de chuva atendem?")
    )

    mo.vstack([_box, _ecdf, _bar])
    return


@app.cell(hide_code=True)
def _(mo):
    btn_export_chamados = mo.ui.run_button(label="💾 Exportar chamados_por_bacia.parquet + chamados_enchente_todos.parquet")
    mo.vstack([mo.md("## Export"), btn_export_chamados])
    return (btn_export_chamados,)


@app.cell
def _(btn_export_chamados, df_enc_com_flag, df_enchente_confirmado, mo, pl):
    mo.stop(not btn_export_chamados.value)

    # --- chamados_por_bacia.parquet: apenas confirmados (usado pela análise de AUC) ---
    _df_confirmados = df_enchente_confirmado.filter(pl.col("confirmado_chuva"))
    _df_excluidos = df_enchente_confirmado.filter(~pl.col("confirmado_chuva"))
    _n_dias_conf = _df_confirmados.with_columns(pl.col("dt_abertura").dt.date()).select("dt_abertura").unique().height
    _n_dias_excl = _df_excluidos.with_columns(pl.col("dt_abertura").dt.date()).select("dt_abertura").unique().height

    _df_conf = _df_confirmados.select([
        "dt_abertura", "bairro", "bacia", "servico_solicitado",
        pl.col("latitude").cast(pl.Float64),
        pl.col("longitude").cast(pl.Float64),
    ])
    _df_conf.write_parquet("dados/chamados_por_bacia.parquet")

    # --- chamados_enchente_todos.parquet: todos os 809.x com flag confirmado_chuva ---
    _df_todos = df_enc_com_flag.select([
        "dt_abertura", "bairro", "bacia", "servico_solicitado",
        pl.col("latitude").cast(pl.Float64),
        pl.col("longitude").cast(pl.Float64),
        "confirmado_chuva",
    ])
    _df_todos.write_parquet("dados/chamados_enchente_todos.parquet")

    mo.vstack([
        mo.callout(
            mo.md(f"Exportado **chamados_por_bacia.parquet** — {len(_df_conf):,} confirmados em {_n_dias_conf} dias."),
            kind="success",
        ),
        mo.callout(
            mo.md(f"Exportado **chamados_enchente_todos.parquet** — {len(_df_todos):,} chamados totais ({len(_df_conf):,} confirmados, {len(_df_excluidos):,} sem chuva)."),
            kind="success",
        ),
    ])
    return


if __name__ == "__main__":
    app.run()
