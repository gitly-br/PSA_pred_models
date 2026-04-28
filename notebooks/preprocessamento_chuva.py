import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    import json
    import marimo as mo
    from datetime import datetime
    return datetime, json, mo, pl


@app.cell
def _(json, pl):
    with open("dados/estacoes_bacia.json") as _f:
        estacoes_bacia = json.load(_f)

    _resumo = pl.DataFrame([
        {"bacia": b, "n_estacoes": len(ests)}
        for b, ests in estacoes_bacia.items()
    ])
    return (estacoes_bacia,)


@app.cell
def _(mo):
    mo.md("""
    ## Preprocessamento de chuva por bacia

    Para cada bacia, gera um parquet com grid horário completo (2016–2025) × estações selecionadas pelo score.
    Horas sem leitura recebem `0`. Output: `dados/chuva_bacias/chuva_{bacia}.parquet`.
    """)
    return


@app.cell
def _(datetime, estacoes_bacia, mo, pl):
    _INICIO = datetime(2016, 1, 1, 0, 0)
    _FIM    = datetime(2025, 12, 31, 23, 0)

    _resultados = []

    for _bacia, _estacoes in estacoes_bacia.items():
        # Grid completo: todas as horas × todas as estações da bacia
        _df_horas = pl.DataFrame({
            "hora": pl.datetime_range(_INICIO, _FIM, interval="1h", eager=True)
        })
        _df_est = pl.DataFrame({"codEstacao": _estacoes})
        _grid = _df_horas.join(_df_est, how="cross")

        # CEMADEN filtrado às estações da bacia, truncado por hora
        _cemaden = (
            pl.scan_parquet("dados/cemaden_abcd.parquet")
            .filter(pl.col("codEstacao").is_in(_estacoes))
            .filter(pl.col("valor_mm").is_not_null() & (pl.col("valor_mm") >= 0))
            .with_columns(pl.col("dt").dt.truncate("1h").alias("hora"))
            .group_by(["hora", "codEstacao"])
            .agg(pl.col("valor_mm").max().alias("valor_mm"))
            .collect()
        )

        # Join no grid → preenche ausências com 0 → pivot para formato largo
        _wide = (
            _grid
            .join(_cemaden, on=["hora", "codEstacao"], how="left")
            .with_columns(pl.col("valor_mm").fill_null(0))
            .pivot(on="codEstacao", index="hora", values="valor_mm")
            .sort("hora")
        )

        _path = f"dados/chuva_bacias/chuva_{_bacia}.parquet"
        _wide.write_parquet(_path)

        _resultados.append({
            "bacia": _bacia,
            "estacoes": len(_estacoes),
            "horas": len(_wide),
            "arquivo": _path,
        })

    df_resumo = pl.DataFrame(_resultados)
    mo.vstack([
        mo.callout(mo.md("Arquivos gerados com sucesso."), kind="success"),
        mo.ui.table(df_resumo),
    ])
    return (df_resumo,)


if __name__ == "__main__":
    app.run()
