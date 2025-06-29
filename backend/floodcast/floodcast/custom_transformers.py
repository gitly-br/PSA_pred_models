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
        n_blocks = len(X) // self.BLOCK
        if n_blocks == 0:
            raise ValueError("Precisamos de pelo menos 24 linhas.")

        rows     = []
        dt_bases = []
        # gera blocos completos
        for b in range(n_blocks):
            start = b * self.BLOCK
            block = X.iloc[start : start + self.BLOCK]
            dt_bases.append(block["dt"].iloc[0])
            # ** aqui passamos X e start para o _agg_block **
            rows.append(self._agg_block(X, start))

        # bloco final parcial opcional
        if not self.drop_partial:
            tail = len(X) % self.BLOCK
            if tail:
                start = n_blocks * self.BLOCK
                block = X.iloc[start:]
                dt_bases.append(block["dt"].iloc[0])
                rows.append(self._agg_block(X, start))

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
                    win_start = block_start + start
                    win_end   = win_start + self.BLOCK
                    if win_end > len(arr_full):
                        if self.drop_partial:
                            continue
                        win_end = len(arr_full)

                    segment = arr_full[win_start:win_end]
                    if segment.size == 0:
                        continue
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