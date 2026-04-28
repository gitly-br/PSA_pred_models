import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    import polars as pl
    import marimo as mo
    import altair as alt

    return alt, json, mo, pl


@app.cell
def _():
    JANELAS_H = [1, 3, 6, 24, 48, 72]
    LOOKBACK_H = 72
    return JANELAS_H, LOOKBACK_H


@app.cell
def _(json, pl):
    df_chamados_raw = pl.read_parquet("dados/chamados_enchente_todos.parquet")
    with open("dados/estacoes_bacia.json") as _f:
        estacoes_bacia = json.load(_f)
    return df_chamados_raw, estacoes_bacia


@app.cell(hide_code=True)
def _(estacoes_bacia, mo):
    sel_bacia = mo.ui.radio(
        options=sorted(estacoes_bacia.keys()),
        value=sorted(estacoes_bacia.keys())[0],
        label="Bacia",
        inline=True,
    )
    mo.vstack([
        mo.md("""
        # Validação de Chamados por Bacia

        Reconfirmação dos chamados 809.x usando apenas estações CEMADEN da bacia hidrográfica.
        Mostra todos os chamados filtrados por bacia, separados em três categorias:
        confirmados pela bacia, confirmados cidade-wide que caem com o filtro local, e sem confirmação de chuva.
        """),
        sel_bacia,
    ])
    return (sel_bacia,)


@app.cell(hide_code=True)
def _(mo):
    n_1h  = mo.ui.number(start=1,  stop=150, step=1, value=20,  label="01h")
    n_3h  = mo.ui.number(start=5,  stop=200, step=1, value=30,  label="03h")
    n_6h  = mo.ui.number(start=5,  stop=300, step=1, value=45,  label="06h")
    n_24h = mo.ui.number(start=5,  stop=300, step=1, value=60,  label="24h")
    n_48h = mo.ui.number(start=5,  stop=300, step=1, value=80,  label="48h")
    n_72h = mo.ui.number(start=5,  stop=300, step=1, value=100, label="72h")
    mo.vstack([
        mo.md("**Limiares de confirmação por janela (mm)**"),
        mo.hstack([n_1h, n_3h, n_6h, n_24h, n_48h, n_72h], widths="equal"),
    ])
    return n_1h, n_24h, n_3h, n_48h, n_6h, n_72h


@app.cell
def _(n_1h, n_24h, n_3h, n_48h, n_6h, n_72h):
    lims = {
        1: n_1h.value, 3: n_3h.value, 6: n_6h.value,
        24: n_24h.value, 48: n_48h.value, 72: n_72h.value,
    }
    return (lims,)


@app.cell
def _(df_chamados_raw, sel_bacia):
    df_chamados_bacia = df_chamados_raw.filter(
        df_chamados_raw["bacia"] == sel_bacia.value
    )
    return (df_chamados_bacia,)


@app.cell
def _(estacoes_bacia, pl, sel_bacia):
    _estacoes = estacoes_bacia[sel_bacia.value]
    df_cemaden_bacia_horario = (
        pl.scan_parquet("dados/cemaden_abcd.parquet")
        .filter(pl.col("codEstacao").is_in(_estacoes))
        .filter(pl.col("valor_mm").is_not_null() & (pl.col("valor_mm") >= 0))
        .with_columns(pl.col("dt").dt.truncate("1h").alias("hora"))
        .group_by("hora")
        .agg(pl.col("valor_mm").max().alias("chuva_max_mm"))
        .sort("hora")
        .collect()
    )
    return (df_cemaden_bacia_horario,)


@app.cell
def _(
    JANELAS_H,
    LOOKBACK_H,
    df_cemaden_bacia_horario,
    df_chamados_bacia,
    lims,
    pl,
):
    from functools import reduce as _reduce

    _chamados_idx = (
        df_chamados_bacia
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
            df_cemaden_bacia_horario,
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

    _cond_bacia = _reduce(
        lambda a, b: a | b,
        [pl.col(f"acc_{h}h").fill_null(0) >= lims[h] for h in JANELAS_H],
    )

    df_chamados_confirmado = (
        df_chamados_bacia
        .drop_nulls("dt_abertura")
        .with_row_index("_idx")
        .join(_accs, on="_idx", how="left")
        .drop("_idx")
        .with_columns(_cond_bacia.alias("confirmado_chuva_bacia"))
    )
    return (df_chamados_confirmado,)


@app.cell(hide_code=True)
def _(df_chamados_confirmado, mo, pl, sel_bacia):
    _n_total    = len(df_chamados_confirmado)
    _n_conf     = int(df_chamados_confirmado["confirmado_chuva_bacia"].sum())
    _n_amarelo  = int(
        df_chamados_confirmado
        .filter(pl.col("confirmado_chuva") & ~pl.col("confirmado_chuva_bacia"))
        .height
    )
    _n_vermelho = int(df_chamados_confirmado.filter(~pl.col("confirmado_chuva")).height)

    def _n_dias(mask):
        return (
            df_chamados_confirmado
            .filter(mask)
            .with_columns(pl.col("dt_abertura").dt.date().alias("_d"))
            ["_d"].n_unique()
        )

    _n_dias_total   = _n_dias(pl.lit(True))
    _n_dias_conf    = _n_dias(pl.col("confirmado_chuva_bacia"))
    _n_dias_amarelo = _n_dias(pl.col("confirmado_chuva") & ~pl.col("confirmado_chuva_bacia"))
    _n_dias_verm    = _n_dias(~pl.col("confirmado_chuva"))

    mo.vstack([
        mo.md(f"### Bacia **{sel_bacia.value}**"),
        mo.hstack([
            mo.stat(value=f"{_n_total:,}",    label="Total de chamados",           bordered=True),
            mo.stat(value=f"{_n_conf:,}",     label="🟢 Confirmados pela bacia",   bordered=True),
            mo.stat(value=f"{_n_amarelo:,}",  label="🟡 Caem com filtro de bacia", bordered=True),
            mo.stat(value=f"{_n_vermelho:,}", label="🔴 Sem confirmação de chuva", bordered=True),
        ], widths="equal"),
        mo.hstack([
            mo.stat(value=str(_n_dias_total),   label="Dias com chamados",         bordered=True),
            mo.stat(value=str(_n_dias_conf),    label="🟢 Dias confirmados",       bordered=True),
            mo.stat(value=str(_n_dias_amarelo), label="🟡 Dias que caem",          bordered=True),
            mo.stat(value=str(_n_dias_verm),    label="🔴 Dias sem chuva",         bordered=True),
        ], widths="equal"),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Distribuição temporal

    Clique num ponto para inspecionar o perfil de chuva das 72h anteriores.
    🟢 **Verde** = confirmado pelas estações da bacia.
    🟡 **Amarelo** = era confirmado cidade-wide mas cai com estações locais.
    🔴 **Vermelho** = sem confirmação de chuva em nenhuma estação.
    """)
    return


@app.cell
def _(alt, df_chamados_confirmado, mo, pl):
    _df_diario = (
        df_chamados_confirmado
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .group_by("data")
        .agg([
            pl.len().alias("n_chamados"),
            pl.col("confirmado_chuva_bacia").sum().alias("n_conf_bacia"),
            pl.col("confirmado_chuva").sum().alias("n_conf_cidade"),
        ])
        .sort("data")
        .with_columns(
            pl.when(pl.col("n_conf_bacia") > 0)
            .then(pl.lit("Confirmado pela bacia"))
            .when(pl.col("n_conf_cidade") > 0)
            .then(pl.lit("Cai com filtro de bacia"))
            .otherwise(pl.lit("Sem confirmação de chuva"))
            .alias("status")
        )
    )

    _dominio = ["Confirmado pela bacia", "Cai com filtro de bacia", "Sem confirmação de chuva"]
    _cores   = ["#2ca02c", "#f5c400", "#d62728"]

    _chart = (
        alt.Chart(_df_diario)
        .mark_circle(size=80, opacity=0.85)
        .encode(
            x=alt.X("data:T", title="Data", axis=alt.Axis(format="%Y", tickCount="year")),
            y=alt.Y("n_chamados:Q", title="Chamados no dia"),
            color=alt.Color(
                "status:N",
                scale=alt.Scale(domain=_dominio, range=_cores),
                legend=alt.Legend(title="Confirmação por bacia", orient="bottom"),
            ),
            tooltip=[
                alt.Tooltip("data:T", title="Data", format="%d/%m/%Y"),
                alt.Tooltip("n_chamados:Q", title="Chamados"),
                alt.Tooltip("n_conf_bacia:Q", title="Conf. pela bacia"),
                alt.Tooltip("n_conf_cidade:Q", title="Conf. cidade-wide"),
            ],
        )
        .properties(width="container", height=280)
        .interactive()
    )

    chart_chamados_bacia = mo.ui.altair_chart(_chart)
    chart_chamados_bacia
    return


if __name__ == "__main__":
    app.run()
