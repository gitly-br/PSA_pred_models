import numpy as np
import pandas as pd
from scipy.stats import mode
from sklearn.base import BaseEstimator, TransformerMixin

# ---------- estatísticas vetorizadas ----------
def _delta(a):
    return np.nanmax(a, axis=-1) - np.nanmin(a, axis=-1)

STAT_FUNCS = {
    "mean":   lambda a: np.nanmean(a, axis=-1),
    "median": lambda a: np.nanmedian(a, axis=-1),
    "sum":    lambda a: np.nansum(a, axis=-1),
    "max":    lambda a: np.nanmax(a, axis=-1),
    "min":    lambda a: np.nanmin(a, axis=-1),
    "delta":  _delta,
    "mode":   lambda a: mode(a, axis=-1, keepdims=False).mode
}

class WindowAgg(BaseEstimator, TransformerMixin):
    """
    Para cada bloco de 24 linhas, agrega as features e anexa um 'dt_base'.
    """
    BLOCK = 24

    def __init__(self, agg_config, drop_partial=True):
        self.agg_config   = agg_config
        self.drop_partial = drop_partial

    def fit(self, X, y=None):
        if "dt" not in X.columns:
            raise KeyError("É preciso ter coluna 'dt' no DataFrame de entrada.")
        return self

    def transform(self, X):
        X = X.reset_index(drop=True)
        agg_start = self.agg_config.get("start")
        for feature in self.agg_config:
            for agg, config in self.agg_config[feature].items():
                if 'start' in config:
                    agg_start = config['start']
        rows     = []
        dt_bases = []
        # gera blocos completos
        block = X.iloc[agg_start : agg_start + 24]
        dt_bases.append(block["dt"].iloc[0])
        # ** aqui passamos X e start para o _agg_block **
        rows.append(self._agg_block(X, 0))

        df_feat = pd.DataFrame(rows)
        df_feat["dt"] = pd.to_datetime(dt_bases)
        return df_feat

    def _agg_block(self, X, block_start):
        """
        Agora recebe:
         - X: DataFrame inteiro
         - block_start: índice da linha inicial do bloco
        """
        out = {}
        for feats, spec in self.agg_config.items():
            feats = (feats,) if isinstance(feats, str) else feats
            for col in feats:
                if col not in X.columns:
                    raise KeyError(f"Coluna '{col}' ausente")
                arr_full = X[col].to_numpy()

                for agg_name, p in spec.items():
                    func  = STAT_FUNCS[agg_name]
                    step  = p["step"]
                    start = p["start"]

                    # janela absoluta
                    segment = arr_full[block_start:block_start + 24]
                    # reshape em janelas de 'step'
                    n_win = len(segment) // step
                    seg   = segment[: n_win * step].reshape(n_win, step)

                    vals = func(seg)
                    for i, v in enumerate(vals):
                        s = start + i * step
                        e = s + step
                        out[f"{col}_{agg_name}_{s}_{e}"] = v
        return out

class DropColumnsTransformer(BaseEstimator, TransformerMixin):
    """
    Transformer que remove colunas especificadas.
    """
    def __init__(self, columns):
        self.columns = columns

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X.drop(columns=self.columns)
