"""
Diagnóstico dos FPs de nível ≥3 (graves) do V7 GradBoost.

Para tamanduatei e guarara, listar:
- Dias no test set classificados como grave (alarme ≥3) cuja severidade real era 0, 1 ou 2.
- Características: chuva máxima, acumulado 24h, n_chamados, fonte externa, dia da semana.
- Hipóteses testadas:
  * Chuva forte sem chamado (teto estrutural / drenagem)
  * Chuva normal com modelo errando (overfit)
  * Dia próximo a evento real (off-by-one)
"""
import polars as pl
import numpy as np
import warnings
import json
from datetime import datetime, date
from functools import reduce
from scipy.signal import lfilter

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import precision_recall_curve

# replica do setup V7 (apenas o necessário)
exec(open("_run_modelos_v7.py").read().split("def thr_por_f1_cv_simples")[0])

# v7 já produziu df_ml com colunas: data, bacia, n_chamados, pos_externo, max_dia,
# severidade, enchente, + features V4
print("\n========== Diagnóstico FPs grave (nivel ≥3) ==========")

def _thr_por_f1(y, p):
    pr, rc, th = precision_recall_curve(y, p)
    if len(th) == 0: return 0.5
    f1s = (2*pr[:-1]*rc[:-1]) / (pr[:-1]+rc[:-1]+1e-9)
    return float(th[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5

def _thr_cv_f1(X_tr, y_tr_bin, sw_arr, n_splits=5):
    tscv = TimeSeriesSplit(n_splits=n_splits)
    oof = np.full(len(y_tr_bin), np.nan)
    for tr, va in tscv.split(X_tr):
        if y_tr_bin[tr].sum() == 0 or y_tr_bin[va].sum() == 0:
            continue
        clf = GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=2, min_samples_leaf=10,
            subsample=0.8, max_features="sqrt", random_state=42,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf.fit(X_tr.iloc[tr], y_tr_bin[tr], sample_weight=sw_arr[tr])
        oof[va] = clf.predict_proba(X_tr.iloc[va])[:, 1]
    mask = ~np.isnan(oof)
    if mask.sum() == 0 or y_tr_bin[mask].sum() == 0:
        return 0.5
    return _thr_por_f1(y_tr_bin[mask], oof[mask])

def w_fit_m3(sev):
    return np.where(sev == 3, 3.0, np.where(sev == 2, 1.5, 1.0)).astype(float)

linhas_diag = []
for bacia in ["guarara", "tamanduatei"]:
    t_cut = T_CUT_ORATORIO if bacia == "oratorio" else T_CUT
    sub = df_ml.filter(pl.col("bacia") == bacia).drop_nulls(FEATURES_V4)
    train = sub.filter(pl.col("data") < t_cut)
    test  = sub.filter(pl.col("data") >= t_cut)
    X_tr = train[FEATURES_V4].to_pandas()
    X_te = test[FEATURES_V4].to_pandas()
    sev_tr = train["severidade"].to_numpy()
    sev_te = test["severidade"].to_numpy()

    # treinar 3 modelos binários como no V7
    probs_te = {}
    thrs = {}
    for k in [1, 2, 3]:
        y_tr_bin = (sev_tr >= k).astype(int)
        sw = w_fit_m3(sev_tr) if k == 3 else np.ones(len(sev_tr))
        thr = _thr_cv_f1(X_tr, y_tr_bin, sw)
        clf = GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=2, min_samples_leaf=10,
            subsample=0.8, max_features="sqrt", random_state=42,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf.fit(X_tr, y_tr_bin, sample_weight=sw)
        probs_te[k] = clf.predict_proba(X_te)[:, 1]
        thrs[k] = thr

    alarme_nivel = np.zeros(len(sev_te), dtype=int)
    for k in [1, 2, 3]:
        alarme_nivel = np.where(probs_te[k] >= thrs[k], k, alarme_nivel)

    # FPs de nível ≥3: alarme=3 mas sev<3
    fp_mask = (alarme_nivel == 3) & (sev_te < 3)
    print(f"\n{bacia.upper()}: thresholds m1={thrs[1]:.3f} m2={thrs[2]:.3f} m3={thrs[3]:.3f}")
    print(f"  Total alarmes ≥3: {(alarme_nivel == 3).sum()}")
    print(f"  TPs (sev=3 e alarme=3): {((sev_te == 3) & (alarme_nivel == 3)).sum()}")
    print(f"  FPs (sev<3 e alarme=3): {fp_mask.sum()}")

    # detalhar cada FP
    test_pd = test.to_pandas()
    fp_df = test_pd[fp_mask].copy()
    fp_df["prob_m3"] = probs_te[3][fp_mask]
    fp_df["prob_m2"] = probs_te[2][fp_mask]
    fp_df["prob_m1"] = probs_te[1][fp_mask]
    fp_df["bacia_diag"] = bacia
    cols = ["bacia_diag", "data", "severidade", "n_chamados", "pos_externo",
            "max_dia", "acum_7d", "api_085", "prob_m1", "prob_m2", "prob_m3"]
    cols = [c for c in cols if c in fp_df.columns]
    print(f"\nFPs de nível ≥3 em {bacia.upper()}:")
    print(fp_df[cols].sort_values("prob_m3", ascending=False).to_string(index=False))

    # caracterização agregada
    print(f"\n  Distribuição da chuva (max_dia) nos FPs vs eventos reais:")
    print(f"    FPs (n={fp_mask.sum()}):  max_dia médio = {fp_df['max_dia'].mean():.1f} mm  mediano = {fp_df['max_dia'].median():.1f}")
    real_grave = test_pd[sev_te == 3]
    if len(real_grave) > 0:
        print(f"    Reais sev=3 (n={len(real_grave)}): max_dia médio = {real_grave['max_dia'].mean():.1f} mm  mediano = {real_grave['max_dia'].median():.1f}")

    # fonte externa nos FPs?
    if "pos_externo" in fp_df.columns:
        n_ext = int(fp_df["pos_externo"].sum())
        print(f"  FPs com pos_externo=True: {n_ext}/{fp_mask.sum()}")

    # off-by-one: FP está a ≤2 dias de um evento real grave?
    datas_graves = pl.from_pandas(test_pd[sev_te == 3])["data"].to_list()
    if len(datas_graves) > 0:
        off_by_one = 0
        for _, row in fp_df.iterrows():
            d_fp = row["data"]
            for d_g in datas_graves:
                if abs((d_fp - d_g).days) <= 2:
                    off_by_one += 1
                    break
        print(f"  FPs a ≤2 dias de um sev=3 real: {off_by_one}/{fp_mask.sum()}")

    # dia da semana
    fp_df["weekday"] = pl.Series(fp_df["data"]).map_elements(lambda d: d.weekday(), return_dtype=pl.Int8).to_pandas()
    print(f"  Distribuição weekday dos FPs (0=seg, 6=dom):")
    print(fp_df["weekday"].value_counts().sort_index().to_string())

    linhas_diag.append(fp_df[cols].assign(bacia=bacia))
