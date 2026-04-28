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
    from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score
    from sklearn.preprocessing import StandardScaler
    return (
        LogisticRegression,
        RandomForestClassifier,
        StandardScaler,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )


@app.cell
def _():
    JANELAS_H = [1, 3, 6, 24, 48, 72]
    LOOKBACK_H = 72
    MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
    ANO_INICIO_TESTE = 2024
    LIMS = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
    FEATURES = [
        "chuva_24h", "chuva_48h", "chuva_72h", "chuva_7d",
        "chuva_max_1h", "chuva_max_3h", "chuva_max_6h",
        "horas_com_chuva", "dias_desde_ultima_chuva",
    ]
    return ANO_INICIO_TESTE, FEATURES, JANELAS_H, LIMS, LOOKBACK_H, MESES_CHUVOSOS


if __name__ == "__main__":
    app.run()
