---
jupyter:
  jupytext:
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.18.1
  kernelspec:
    display_name: Python 3 (ipykernel)
    language: python
    name: python3
---

<!-- #region id="0rtkthIAVcyI" -->
# Introdução teste

<!-- #endregion -->

<!-- #region id="sM_WhFUSYdOf" -->
# Objetivos

* Considerando os dados do CEMADEN, fazer um modelo que é capaz de prever eventos com chamados.
<!-- #endregion -->

<!-- #region id="PNw8nMGfUEKk" -->
# TODO
<!-- #endregion -->

<!-- #region id="mYl31uoCajO9" -->
* [X] Verificar diferença entre conjunto de validação aleatório vs por ano
* [X] Variar métricas de agregados
* [X] Variar métricas de agregados
* [X] Clusterizar para verificar relação entre pontos com enchente e sem. (plotly scatter 3D)
* [x] Undersampling com k alto
* [x] Agregado de média de maiores estações

Foco
* []  Coagir chamados para dias com chuvas acima do normal (testar vários recortes)
  * [] Testar clusterização para verificar "fake trues"
  * [] Recorte por percentil de chuva (começar pelos casos mais extremos)
* [] Coagir dias com pouca chuva e chamado para não ter chamado (testar vários recortes)

P/ depois
* [] Confirmar estações para cada bacia (olhar nos mapas)
* [] Testar modelos específicos para outras bacias (além de Tam.)
* [] Definição de chuva de alto risco E
<!-- #endregion -->

<!-- #region id="gJVzrY0PdkuB" -->
# Importa libs e define funções
<!-- #endregion -->

```python colab={"base_uri": "https://localhost:8080/", "height": 315} id="jhYcEZcdCmnF" outputId="ed992177-4137-4a24-9aad-18243df641d2"
# Pycaret
!pip install --upgrade packaging -q
!pip install pycaret[full] -q

from pycaret.classification import *
```

```python id="KhYDMG7v7_KE"
# File management
import zipfile
import gdown
import os
import numpy as np

# Data manipulation
import pandas as pd

# Data splitting
from sklearn.model_selection import train_test_split

# Sampling techniques
from imblearn.under_sampling import ClusterCentroids

# Plotting
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.cluster import KMeans
```

```python id="QoXjmGMKduZG"
def grab_from_gdrive(file_id, filename):
  parent_dir = '/content'
  url = f"https://drive.google.com/uc?id={file_id}"
  output = os.path.join(parent_dir, filename)
  if not(os.path.isfile(output)):
    gdown.download(url, output=output, quiet=False)
```

```python id="m5iYTo9vPjX5"
def cluster_undersample(df, target_column, resample_strength, samples_per_cluster):
    """
    Performs undersampling on the majority class (assumed False) using KMeans clustering.

    Args:
        df (pd.DataFrame): The input DataFrame.
        target_column (str): The name of the target column (boolean).
        resample_proportion (float): The desired proportion of the minority class
                                     (True) in the resampled dataset (between 0 and 1).
        samples_per_cluster (int): The number of samples to take from each cluster
                                   of the majority class.

    Returns:
        pd.DataFrame: The resampled DataFrame.
    """
    df_true = df[df[target_column] == True].copy()
    df_false = df[df[target_column] == False].copy()

    # Calculate the number of true instances
    num_true = len(df_true)
    num_false = len(df_false)

    desired_num_false = int(num_false / resample_strength)
    num_clusters = max(1, int(desired_num_false / samples_per_cluster))

    print(f"Number of true instances: {num_true}")
    print(f"Desired number of false instances: {desired_num_false}")
    print(f"Calculated number of clusters: {num_clusters}")
    print(f"Samples per cluster: {samples_per_cluster}")

    if num_clusters > len(df_false):
        print(f"Warning: Calculated number of clusters ({num_clusters}) is greater than the number of false instances ({len(df_false)}). Setting number of clusters to the number of false instances.")
        num_clusters = len(df_false)
        samples_per_cluster = 1 # Adjust samples per cluster to avoid errors

    if num_clusters == 0:
        print("Warning: No clusters will be created as the desired number of false instances is 0.")
        return df_true

    # Apply KMeans clustering to the majority class
    # Exclude non-numeric columns like 'dt' if it exists
    feature_columns = df_false.select_dtypes(include=np.number).columns
    if 'dt' in df_false.columns:
        feature_columns = feature_columns.drop('dt', errors='ignore')
    if target_column in feature_columns:
        feature_columns = feature_columns.drop(target_column, errors='ignore')


    if len(feature_columns) == 0:
         raise ValueError("No numeric features available for clustering.")


    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    kmeans.fit(df_false[feature_columns])
    df_false['cluster'] = kmeans.labels_

    # Sample from each cluster
    df_false_resampled = pd.DataFrame()
    for cluster_label in range(num_clusters):
        cluster_data = df_false[df_false['cluster'] == cluster_label]
        if not cluster_data.empty:
            # Sample min(samples_per_cluster, actual number of samples in cluster)
            sampled_cluster_data = cluster_data.sample(n=min(samples_per_cluster, len(cluster_data)), random_state=42)
            df_false_resampled = pd.concat([df_false_resampled, sampled_cluster_data], ignore_index=True)

    # Combine the resampled majority class with the minority class
    df_resampled = pd.concat([df_true, df_false_resampled.drop(columns=['cluster'], errors='ignore')], ignore_index=True)

    return df_resampled
```

<!-- #region id="QqO-4HH0kpFN" -->
# Carrega dados CEMADEN

* Carrega dados do google drive com daily metrics
<!-- #endregion -->

```python id="Z96nCxhPaFK0"
file_agregado_cemaden = 'df_daily_metrics.csv'
grab_from_gdrive('1wYMSPeli7S2QiZQl0WJR4r3E7u41hQRZ', file_agregado_cemaden)
df_daily_metrics = pd.read_csv(file_agregado_cemaden)
```

<!-- #region id="73WXCXXyCFMh" -->
# Carrega datas de enchentes verificadas
<!-- #endregion -->

```python colab={"base_uri": "https://localhost:8080/"} id="KR3vH2plCOm4" outputId="1175caab-e627-4ff8-b86e-03a1039ccd65"
file_enchentes = 'df_enchentes_verificados.csv'
grab_from_gdrive('1GDKraiiulvZ0_H-SWMiN76GnDn9lE_9T', file_enchentes)
df_enchentes_verificados = pd.read_csv(file_enchentes)
```

<!-- #region id="J8bjLsJ6HgW8" -->
# Faz o merge dos datasets

* Agrega dados de chuva por data pela soma, remove colunas em que essa agregação não faz sentido
* Remove meses tipicamente sem chuva (entre 5 e 10)
* Adiciona coluna de enchente, verificando se houve enchente no dataset de enchentes
<!-- #endregion -->

```python id="KyjcpUDVH2sZ"
df_dm_grouped = df_daily_metrics.groupby(["ano", "mes", "dia"]).sum().reset_index()
df_dm_grouped.drop(columns=["latitude", "longitude", "coef_var", "perc_chuva_em_3h", "nomeEstacao"], inplace=True)
```

```python id="giwg6GtrIJEO"
df_dm_dt = df_dm_grouped.copy()
df_dm_dt['dt'] = pd.to_datetime(df_dm_dt.apply(lambda row: f"{int(row['dia']):02}/{int(row['mes']):02}/{int(row['ano'])}", axis=1), dayfirst=True)
df_dm_dt.drop(columns=["ano", "mes", "dia"], inplace=True)
```

```python id="r7dXC_K0MWtN"
df_dm_sazonal = df_dm_dt[~df_dm_dt["dt"].dt.month.between(5, 10)].copy()
```

```python id="D3q2rYVlIglk"
df_dm_enchentes = df_dm_sazonal.copy()
df_dm_enchentes['enchente'] = df_dm_enchentes['dt'].isin(df_enchentes_verificados['dt'])
```

<!-- #region id="QJRAB2ZVBgG8" -->
# Testa com configuração padrão

* Modelo com chamados novos
* Usa dataset CEMADEN
* Sem rebalanceamento

Melhores modelos obtidos:

| Model | Description                    | Accuracy |   AUC   | Recall | Prec. |   F1   | Kappa  |  MCC   | TT (Sec) |
|-------|--------------------------------|----------|--------|--------|-------|--------|--------|--------|----------|
| qda   | Quadratic Discriminant Analysis| 0.9209   | 0.8127 | 0.4491 | 0.2991| **0.3540** | **0.3150** | 0.3246 | 0.0280   |
| nb    | Naive Bayes                    | 0.9130   | 0.8172 | **0.4709** | 0.2744| 0.3440 | 0.3023 | 0.3157 | 0.0240   |
| lda   | Linear Discriminant Analysis   | **0.9403** | **0.8284** | 0.3182 | **0.3488**| 0.3307 | 0.2997 | **0.3011** | **0.0240**   |

Os modelos que aparecem aí são modelos resistentes a desbalanceamento, mas mesmo eles estão com característica de modelo desbalanceado. Não faz sentido continuar sem balanceamento.
<!-- #endregion -->

```python id="BnsF1j_JEIeR"
X = df_dm_enchentes.drop(columns=["dt", "enchente"])
y = df_dm_enchentes["enchente"]
```

```python colab={"base_uri": "https://localhost:8080/", "height": 583} id="qriGK0vEEecY" outputId="c6baf2af-23ee-429c-c168-3decd814f79c"
s = setup(data=X, target=y, session_id=123, fix_imbalance=False, fold=5, imputation_type=None)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 520, "referenced_widgets": ["cb23f118de2f4ebe85a8552c3cbe4cd9", "4be56f990c4f44afb56a11fb54c8df3d", "049d70c821174d77a76e503c3fe9cce6", "a6043daa44d34ea89e0d4ae1cadbf100", "7b281f54ced74f3ebd62bbc8935ce6ce", "048a7138c06e4595bd3d8822d86493aa", "e45d3123462c4b9fbb4982f5d1c87db2", "822acf28cf6948d4b2af8c8a8c1073d1", "70cf702bf46547568036df6875598078", "799cdfa0be11480b96527eb63441b7d5", "003030a3f0d3470295ce26ce1ba61e5f"]} id="acA3Vj8IGgvX" outputId="2cb33f05-f3b0-4a84-e30f-6cba3d388ada"
best_model = compare_models(n_select=1, sort="F1")
```

<!-- #region id="SOjrkM0vKBRl" -->
# Testa com rebalanceamento

* Testa todas as técnicas de rebalanceamento do pycaret
<!-- #endregion -->

```python id="nAt_11k8KIVF"
X = df_dm_enchentes.drop(columns=["dt", "enchente"])
y = df_dm_enchentes["enchente"]
```

```python id="vQjEB4nqKghR"
# Undersample the training data using Cluster Centroids
cc = ClusterCentroids(random_state=42, sampling_strategy=1)
X_resampled, y_resampled = cc.fit_resample(X, y)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 663} id="2UpY6ouJKuBu" outputId="8dfc3729-d7c1-4fc7-b3ea-8e8a47b9c150"
setup(data=X, target=y, session_id=123, fix_imbalance=True, fix_imbalance_method="svmsmote", fold=5, imputation_type=None)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 520, "referenced_widgets": ["c5b08cc5e1924045bac88d90f32b6c12", "c3294b4fbec24a1599e622a2b472bfb9", "3e595d43475a456abf28037dccccf1a9", "05ead08c9d5f4c23b64da9a595f4810f", "7ab5b489472f4a34bb12d6cac527dfbe", "35632ff2294243b2a9630dcd4614c827", "5c59228fc69f4e79b72c4c3cbc5f29cc", "0b7cc63f68fc4279b1f944e43ab05f80", "a6b4cb6edc4a4957bdf780d5c7aad80f", "3e9c336075eb44459181ad0a72da7c36", "bf9fef31bfa24a2788d3a40a66e7e398"]} id="IFMevKI9Kxoh" outputId="e9e0726c-9d67-4c5d-98d0-02910e18a026"
best_model = compare_models(n_select=1, sort="F1")
```

```python colab={"base_uri": "https://localhost:8080/", "height": 485, "referenced_widgets": ["3c68b8935f8543039cec1412f57cc430", "882dc9ed095d4563b669b663e487ab88", "f7e7f0dab0bf4429a6710e58ae6fd38d", "8232570ff0c4497883ccb6a348d1bb39", "1cf38b25c7e249f3bbb6f00f4090d634", "be457023329449fab8138dc2f3c54d8a", "7599a1d6e6fb48cda5d6791d9322ec6f", "319c98ca08354e059dc981df1f9658be", "071c9eb622ba4befbbb2702174a54e88", "2dbd1859d2184139abe91f16ff54a1fd", "8b92f0cb899e43dbb7fb64393b204d71"]} id="DQWK2iZtK44F" outputId="15eae58a-9675-4d7a-e97f-269f0fd9cfcd"
create_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 1000} id="JaRtlyGPTC-w" outputId="c0ee2ebf-916b-46d8-9e36-73125939594c"
predict_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 217, "referenced_widgets": ["59e8e6d61fe240b2b5d73da542aac18f", "1ce7324d16c744ffbbc5bca9375c3d30", "4667100bc26b47fd8920297bdf6e6bc0", "f2d0df2d781c4c00bd50330c50171afe", "38f173a4b6c74c2494c665c312a58890", "804466fc2b174619a9aa0b6bcfeb05f0", "5d088d18da3046b8ac1b43c82183560a"]} id="ZBKves2qR9i1" outputId="08df3635-084d-4bc4-c153-665694869ec5"
evaluate_model(best_model)
```

<!-- #region id="LtH-5KYFdtg8" -->

<!-- #endregion -->

<!-- #region id="TaL8-16il1a2" -->
# Testa com undersampling por clusters

* Validar com dados de 2023 e 2024
* Clusteriza e pega 20 valores reais de cada cluster (não centróide)
* Pycaret sem conjunto de validação

Melhor modelo (DT classifier):

| **Fold** | **Accuracy** |   **AUC**  | **Recall** |  **Prec.** |   **F1**   |  **Kappa**  |   **MCC**   |
| :------: | :----------: | :--------: | :--------: | :--------: | :--------: | :---------: | :---------: |
|     0    |    0.3673    |   0.3838   |   0.5455   |   0.3636   |   0.4364   |   -0.2220   |   -0.2464   |
|     1    |    0.4583    |   0.4685   |   0.5909   |   0.4333   |   0.5000   |   -0.0612   |   -0.0648   |
|     2    |    0.3958    |   0.3995   |   0.4286   |   0.3462   |   0.3830   |   -0.1959   |   -0.2002   |
| **Mean** |  **0.4072**  | **0.4173** | **0.5216** | **0.3810** | **0.4398** | **-0.1597** | **-0.1705** |
|  **Std** |    0.0380    |   0.0368   |   0.0684   |   0.0377   |   0.0478   |    0.0705   |    0.0771   |


Matriz de confusão p/ dados de teste:

| **True Class \ Predicted Class** | **False** | **True** |
| -------------------------------- | :-------: | :------: |
| **False**                        |    195    |    157   |
| **True**                         |     9     |     2    |

<!-- #endregion -->

```python colab={"base_uri": "https://localhost:8080/", "height": 178} id="BHOhXbQ3mxcC" outputId="05a30622-33e4-486d-c63d-8054417e195b"
df_test = df_dm_enchentes[df_dm_enchentes['dt'].dt.year >= 2023]
df_train = df_dm_enchentes[df_dm_enchentes['dt'].dt.year < 2023]
```

```python id="i3NYt8yAnKRE"
df_train_true = df_train[df_train.enchente == True]
```

```python colab={"base_uri": "https://localhost:8080/", "height": 524} id="dBAD0_MvnTFV" outputId="f0d9c61f-f8cd-4754-f81d-3256801f2773"
# prompt: for df_train_false clusterize the dataset and grab 20 random samples from each cluster to add to df_train_resampled, that has all the random picked False data and all the rows where enchente is True. If there is a way to decide automatically the number of clusters, do it

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans

# Determine optimal number of clusters using Elbow method
inertia = []
for i in range(1, 11):
    kmeans = KMeans(n_clusters=i, random_state=42)
    kmeans.fit(df_train_false.drop(columns=['dt', 'enchente']))
    inertia.append(kmeans.inertia_)

# Plot the elbow method
plt.plot(range(1, 11), inertia, marker='o')
plt.title('Elbow Method for Optimal k')
plt.xlabel('Number of clusters')
plt.ylabel('Inertia')
plt.show()

```

```python id="-e8ECV6joOSx"
# Choose the optimal number of clusters (e.g., based on the elbow point)
optimal_k = 4 # Replace with your choice based on the elbow method plot

# Apply KMeans clustering with the optimal k
kmeans = KMeans(n_clusters=optimal_k, random_state=42)
kmeans.fit(df_train_false.drop(columns=['dt', 'enchente']))
df_train_false['cluster'] = kmeans.labels_

df_train_resampled = df_train[df_train.enchente == True].copy()

# Grab 20 random samples from each cluster
for cluster in range(optimal_k):
    cluster_samples = df_train_false[df_train_false['cluster'] == cluster]
    samples_to_add = cluster_samples.sample(n=min(20, len(cluster_samples)), random_state=42)
    df_train_resampled = pd.concat([df_train_resampled, samples_to_add])

# Remove the cluster column
df_train_resampled = df_train_resampled.drop(columns=['cluster'], errors='ignore')
```

```python colab={"base_uri": "https://localhost:8080/", "height": 178} id="KU1Oy9L05u64" outputId="3ab260c0-11d1-43cf-98d6-dd848fa85052"
df_train_resampled.enchente.value_counts()
```

```python id="f21A3FWD6NXu"
X = df_train_resampled.drop(columns=["dt"])
X_test = df_test.drop(columns=["dt"])
```

```python colab={"base_uri": "https://localhost:8080/", "height": 600} id="ls0KZTlO50EO" outputId="36235db6-1d1b-465c-9b04-996df14c6a58"
setup(data=X, target="enchente", session_id=123, fix_imbalance=False, fold=3, imputation_type=None, test_data=X_test)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 520, "referenced_widgets": ["03f7b564f3bb46afb03830738204502f", "965bc581e2284d388541bb43b0c58d46", "7d371322deb241dfa71613b50e3d7970", "47989d32ccac49e0b3787c289dd110f0", "78a3cdd8352a4572b9337223bc084383", "ddb8b315c1014f7e8597a94274dfa9aa", "ad9f05bda97f498f952e26a69834aa26", "a25b904e8870464a8531a75a6b83677f", "5bfb67e832aa4010969077d75388911c", "c19d84b810244bc08955a7f889d88094", "116ed25624ec4dffae62a90ef338fe13"]} id="Isk9Qk5u61XJ" outputId="4eb64804-948d-4edd-e92e-5e3b7c37db34"
best_model = compare_models(n_select=1, sort="F1")
```

```python colab={"base_uri": "https://localhost:8080/", "height": 370, "referenced_widgets": ["0dfd0dc4aff2440ea8e4d55ffeececfb", "8e7a8cb9188c41adb49308087d572a4a", "73cd87474af94841987a3ebe58efb67f", "abcd3c857ad448faa50cadb2bbd1a0d3", "e0b52073f28448e0954f41f7a8f4f1ee", "22cb392fe13c435c90ef895630346f51", "c6dc4b294a2a4ecc80cf4b22224889d7", "bc811709214c493badf82245b33b3e60", "2e252e69d9094b53ac9b5bfc6b390658", "6e7ac2dc80334d22b2f7c3540e405938", "035813cd7abb491b9510a00adc05db6d"]} id="XBeN6NgE7d1R" outputId="7bed4fce-4c66-45e6-e4fe-2b77981f4024"
create_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 665, "referenced_widgets": ["fec8dbaa639f41af99f65a6c48428a47", "1c9a96d467ba4b519fe67de9adec4461", "34da1a857335454995535723ccaf5a23", "db6acee15d7f4757b4a786ac04baaa32", "23f5cf99d8a3439783ae117d68c8f862", "5125d1e55e6d4fbd99a95dbf24fd0a01", "4d491fd229624a67997e66668285de36"]} id="gL2M6W3D7jw6" outputId="d5e44afa-67d4-4f5f-b6f2-f2e0a6be1015"
evaluate_model(best_model)
```

<!-- #region id="Oj_ym1HIAhgC" -->
# Refaz merge com agregados CEMADEN

* Usa max para todas as colunas, menos chuva_total, que continua com soma
<!-- #endregion -->

```python id="sWwiPKKfA7pc"
df_dm_grouped_new = df_daily_metrics.groupby(["ano", "mes", "dia"]).agg({
    "chuva_total": "sum",
    "chuva_max_1h": "max",
    "chuva_max_3h": "max",
    "horas_com_chuva": "max",
    "horas_intensas_10mm": "max",}).reset_index()
```

```python id="cqV7Dv_vA7pg"
df_dm_dt = df_dm_grouped_new.copy()
df_dm_dt['dt'] = pd.to_datetime(df_dm_dt.apply(lambda row: f"{int(row['dia']):02}/{int(row['mes']):02}/{int(row['ano'])}", axis=1), dayfirst=True)
df_dm_dt.drop(columns=["ano", "mes", "dia"], inplace=True)
```

```python id="IChmnN4iA7pj"
df_dm_sazonal = df_dm_dt[~df_dm_dt["dt"].dt.month.between(5, 10)].copy()
```

```python id="hEDFCvF6A7pl"
df_dm_enchentes = df_dm_sazonal.copy()
df_dm_enchentes['enchente'] = df_dm_enchentes['dt'].isin(df_enchentes_verificados['dt'])
```

<!-- #region id="isLxQzaF_qju" -->
# Testa com diferentes agregados

* Usa novo df_dm_enchentes para fazer os testes
* Testa com undersampling por clusters

Melhor modelo (RF)

| **Fold** | **Accuracy** |   **AUC**  | **Recall** |  **Prec.** |   **F1**   |  **Kappa**  |   **MCC**   |
| :------: | :----------: | :--------: | :--------: | :--------: | :--------: | :---------: | :---------: |
|     0    |    0.4082    |   0.3737   |   0.7273   |   0.4103   |   0.5246   |   -0.1163   |   -0.1537   |
|     1    |    0.5833    |   0.5612   |   0.5455   |   0.5455   |   0.5455   |    0.1608   |    0.1608   |
|     2    |    0.4583    |   0.4965   |   0.5714   |   0.4138   |   0.4800   |   -0.0558   |   -0.0590   |
| **Mean** |  **0.4833**  | **0.4771** | **0.6147** | **0.4565** | **0.5167** | **-0.0038** | **-0.0173** |
|  **Std** |    0.0737    |   0.0777   |   0.0803   |   0.0629   |   0.0273   |    0.1190   |    0.1318   |

Matriz confusão teste:

| **True Class \ Predicted Class** | **False** | **True** |
| -------------------------------- | :-------: | :------: |
| **False**                        |    269    |    83    |
| **True**                         |     2     |     9    |

<!-- #endregion -->

```python id="6OKG3lWXCOgV"
df_test = df_dm_enchentes[df_dm_enchentes['dt'].dt.year >= 2023]
df_train = df_dm_enchentes[df_dm_enchentes['dt'].dt.year < 2023]
```

```python id="9AJnskk-COgd"
df_train_false = df_train[df_train.enchente == False]
df_train_true = df_train[df_train.enchente == True]
```

```python colab={"base_uri": "https://localhost:8080/", "height": 524} id="MRTJrOXLCOge" outputId="93ef4756-4d1d-4f1e-fbbe-9c3a2df99fc1"
# prompt: for df_train_false clusterize the dataset and grab 20 random samples from each cluster to add to df_train_resampled, that has all the random picked False data and all the rows where enchente is True. If there is a way to decide automatically the number of clusters, do it

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans

# Determine optimal number of clusters using Elbow method
inertia = []
for i in range(1, 11):
    kmeans = KMeans(n_clusters=i, random_state=42)
    kmeans.fit(df_train_false.drop(columns=['dt', 'enchente']))
    inertia.append(kmeans.inertia_)

# Plot the elbow method
plt.plot(range(1, 11), inertia, marker='o')
plt.title('Elbow Method for Optimal k')
plt.xlabel('Number of clusters')
plt.ylabel('Inertia')
plt.show()

```

```python id="rjXQISptCOgh"
# Choose the optimal number of clusters (e.g., based on the elbow point)
optimal_k = 4 # Replace with your choice based on the elbow method plot

# Apply KMeans clustering with the optimal k
kmeans = KMeans(n_clusters=optimal_k, random_state=42)
kmeans.fit(df_train_false.drop(columns=['dt', 'enchente']))
df_train_false['cluster'] = kmeans.labels_

df_train_resampled = df_train[df_train.enchente == True].copy()

# Grab 20 random samples from each cluster
for cluster in range(optimal_k):
    cluster_samples = df_train_false[df_train_false['cluster'] == cluster]
    samples_to_add = cluster_samples.sample(n=min(20, len(cluster_samples)), random_state=42)
    df_train_resampled = pd.concat([df_train_resampled, samples_to_add])

# Remove the cluster column
df_train_resampled = df_train_resampled.drop(columns=['cluster'], errors='ignore')
```

```python colab={"base_uri": "https://localhost:8080/", "height": 178} id="sycz2hM_COgi" outputId="469076fd-6c4d-4910-f9df-e51995a7b309"
df_train_resampled.enchente.value_counts()
```

```python id="jx6o5MuWCOgk"
X = df_train_resampled.drop(columns=["dt"])
X_test = df_test.drop(columns=["dt"])
```

```python colab={"base_uri": "https://localhost:8080/", "height": 387, "referenced_widgets": ["40f421d35e744f0ea1005ddae91dc33d", "19ad812c5f0a4dd0bd4c8802e6ecc80d", "b39e7cc980804d4c92fb56a8b15f7f74", "2bf68f3413bb483799cce12fa5999717", "d07566468dac400ab9633d736c5eef86", "eb2ea76156b24b33a31a4d652826516e", "0b68e4a090d94531b2418e66c7c832ea", "cb75e29aafff470bab46f606f8a840b9", "580ebe1a20544ef0a0612047d4878426", "f9e09e2187294015819ff349a68394b0", "136efa54e2aa4a2b99007ba234993f99"]} id="FbGBtv_HCOgm" outputId="e614eaf9-4d11-438a-b7be-1d503626055b"
create_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 600} id="DtVEdmmpCOgl" outputId="ddc2902c-a5ad-422f-e8fb-5065de58418b"
setup(data=X, target="enchente", session_id=123, fix_imbalance=False, fold=3, imputation_type=None, test_data=X_test)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 520, "referenced_widgets": ["db5177bb815c47c093674843ca0dd119", "17d0edb5866d415385bddb45e6b20c3a", "2d0726081f9b48e7b9ead9a75659f5ee", "abcfba21a1cd48418167b52e811f43ba", "4cc645449f2949fca49ed4aa4b6118cd", "42fed16ff602408eab8d785eaa13a685", "0035bea294304e068ca4ffc2ebdb1563", "fc7df5c9e7cb4a6bb1d68dff37bf0807", "06641a63cce042b989b6f50b79e3427b", "80992947175b4a148aff55b03752991f", "6586ef78f47b463f8267e5d2ab794833"]} id="izVJwRf-COgl" outputId="92cd77a1-c8ea-4608-d719-f8a76f2de1ea"
best_model = compare_models(n_select=1, sort="F1")
```

```python colab={"base_uri": "https://localhost:8080/", "height": 666, "referenced_widgets": ["481a5b43165a46f780a653c6001d11aa", "7702f3cb65f44a898b4db798f6f88745", "500d65f8092c4854b3dc634555581539", "4e91ff9c255d41b7aec4e15d1fa80a37", "09ab0012351f487c9d16dece769fbab8", "c19667d277014aa295af6e8bcf85c271", "22cf153562ea4e8c98171bd568ca74be"]} id="DbmwX_84COgn" outputId="52208ae5-09c8-45ec-94d0-381b7be1048b"
evaluate_model(best_model)
```

<!-- #region id="nGpaDwnQC9oX" -->
# Verifica clusters

* Para os dados do cemaden_daily (com agregados novos), faz n clusters (cotovelo)
* Verifica se algum cluster tem correlação maior com enchentes
* Verifica distribuição usando plotly scatter 3D
<!-- #endregion -->

```python colab={"base_uri": "https://localhost:8080/"} id="bZpXd7EQLMNV" outputId="d1023033-a3e0-48ae-f175-e885c55fd05b"
df_dm_enchentes.columns
```

```python colab={"base_uri": "https://localhost:8080/", "height": 524} id="eB9Uv6v2H1H3" outputId="2c63f86c-d9d1-40e7-820e-142fb048bd5b"
import matplotlib.pyplot as plt
# Determine optimal number of clusters using Elbow method
inertia = []
for i in range(1, 11):
    kmeans = KMeans(n_clusters=i, random_state=42)
    kmeans.fit(df_dm_enchentes.drop(columns=['dt', 'enchente']))
    inertia.append(kmeans.inertia_)

# Plot the elbow method
plt.plot(range(1, 11), inertia, marker='o')
plt.title('Elbow Method for Optimal k')
plt.xlabel('Number of clusters')
plt.ylabel('Inertia')
plt.show()

# Choose the optimal number of clusters (e.g., based on the elbow point)
optimal_k = 2  # Replace with your choice based on the elbow method plot

# Apply KMeans clustering with the optimal k
kmeans = KMeans(n_clusters=optimal_k, random_state=42)
kmeans.fit(df_dm_enchentes.drop(columns=['dt', 'enchente']))
df_dm_enchentes['cluster'] = kmeans.labels_

```

```python colab={"base_uri": "https://localhost:8080/", "height": 631} id="C_wncGOPKQv7" outputId="e8b20c04-d3dd-490a-dc57-cafd8710613f"
# prompt: show the value counts of enchente for each cluster

# Assuming df_dm_enchentes is already created as in your provided code.
# You'll need to ensure the 'cluster' column is present in your DataFrame.
# If not, re-run the KMeans clustering part of your code.

# Group by cluster and count the occurrences of 'enchente'
cluster_enchente_counts = df_dm_enchentes.groupby('cluster')['enchente'].value_counts()

# Print the value counts
print(cluster_enchente_counts)

# For a more visual representation:
# Unstack the multi-index series for easier plotting/analysis
cluster_enchente_counts_unstacked = cluster_enchente_counts.unstack()

# Optionally, plot the results using a bar chart
import matplotlib.pyplot as plt
cluster_enchente_counts_unstacked.plot(kind='bar')
plt.title('Enchente Value Counts per Cluster')
plt.xlabel('Cluster')
plt.ylabel('Count')
plt.xticks(rotation=0) # Rotate x-axis labels for better readability
plt.legend(title='Enchente')
plt.show()

```

```python colab={"base_uri": "https://localhost:8080/", "height": 542} id="LBjIouwHITSb" outputId="f0957a4d-33e9-47a3-8f3b-7c7fcb8e4709"
# prompt: use plotly 3D scatter to check the distribution with cluster as the color. The 3 axis should be "enchente", "chuva_total" and "chuva_max_1h"

fig = px.scatter_3d(df_dm_enchentes, x='horas_intensas_10mm', y='chuva_total', z='chuva_max_3h', color='enchente')
fig.show()

```

```python colab={"base_uri": "https://localhost:8080/"} id="kgJ6eZ7oeLww" outputId="df20fdbb-efd1-407a-a4b0-cc0a13a0c666"
df_dm_enchentes.columns
```

<!-- #region id="ylzD3oUPMatU" -->
# Divide dados por bacia

* A principio apenas uma bacia (tam_central)
* Filtra df_daily_metrics para ter apenas as estacoes que batem com aquela bacia
* Valida os dados de enchente vendo as metricas de chuva no dia. Serao desconsiderados dias com pouca chuva registrada nas estacoes mesmo que o label seja true
* Consolida um dataset para enchentes em tam_central com os dados cemaden

<!-- #endregion -->

```python id="eDGnAB3xM6O3"
tamanduatei_central = [
    "Cidade São Jorge",
    "Jardim Ipanema",
    "Paraíso",
    "Parque das Nações",
    "Santa Terezinha",
    "Vila Bastos",
    "Vila João Ramalho",
    "Vila Suiça",
    "Vila Vitória",
]
```

```python id="wkwomF9wQEwD"
df_dm_tam_central = df_daily_metrics[df_daily_metrics["nomeEstacao"].isin(tamanduatei_central)].copy()
```

```python colab={"base_uri": "https://localhost:8080/"} id="7UMNswrZQbau" outputId="faf2ad61-8c09-43a2-a85a-351bc3cd85ca"
df_dm_tam_central.columns
```

```python id="wc_nquVSQQB6"
df_dm_tc_grouped = df_dm_tam_central.groupby(["ano", "mes", "dia"]).agg({
    "chuva_total": "sum",
    "chuva_max_1h": "max",
    "chuva_max_3h": "max",
    "horas_com_chuva": "max",
    "horas_intensas_10mm": "max",
  }).reset_index()
```

```python id="GE6DS9ibROgu"
df_dm_tc_dt = df_dm_tc_grouped.copy()
df_dm_tc_dt['dt'] = pd.to_datetime(df_dm_tc_dt.apply(lambda row: f"{int(row['dia']):02}/{int(row['mes']):02}/{int(row['ano'])}", axis=1), dayfirst=True)
df_dm_tc_dt.drop(columns=["ano", "mes", "dia"], inplace=True)
```

```python id="9BLs5IW2ROgw"
df_dm_tc_sazonal = df_dm_tc_dt[~df_dm_tc_dt["dt"].dt.month.between(5, 10)].copy()
```

```python id="5CGKgAuuROgx"
df_tc_enchentes = df_dm_tc_sazonal.copy()
df_tc_enchentes['enchente'] = df_tc_enchentes['dt'].isin(df_enchentes_verificados['dt'])
```

<!-- #region id="As744cCgRzK1" -->
Remove dias com nenhuma chuva
<!-- #endregion -->

```python colab={"base_uri": "https://localhost:8080/"} id="0Ino9FdfU59G" outputId="bfb64c81-de24-428c-b81c-5cc265173fd2"
# prompt: from df_tc_enchentes change every label where enchentes is true but any of chuva_total, chuva_max_1h, chuva_max_3h, horas_com_chuva is less than or equal to a threshold. The threshold needs to be different for every feature, so make it a dict. Print how many labels were changed. Create a new df for this (df_tc_enchentes_cut)

# Define the thresholds for each feature
thresholds = {
    'chuva_total': 0,
    'chuva_max_1h': 10,
    'chuva_max_3h': 0,
    'horas_com_chuva': 0
}

# Create a copy of the DataFrame to avoid modifying the original
df_tc_enchentes_cut = df_tc_enchentes.copy()

# Initialize a counter for the number of labels changed
labels_changed = 0

# Iterate through the DataFrame
for index, row in df_tc_enchentes.iterrows():
    # Check if 'enchente' is True
    if row['enchente']:
        # Check if any of the specified features are below the threshold
        for feature, threshold in thresholds.items():
            if row[feature] <= threshold:
                # Change the 'enchente' label to False
                df_tc_enchentes_cut.loc[index, 'enchente'] = False
                labels_changed += 1
                break  # Exit the inner loop once a threshold is met

# Print the number of labels changed
print(f"{labels_changed} labels were changed.")

```

<!-- #region id="1uTQYUNyTUK1" -->
# Testa modelo Tam central

* Usa dataset cemaden atualizado com apenas estacoes tam central
* Usa undersampling por clusters
* Usa agregados novos


**Considerando threshold de 0**

| **True Class \ Predicted Class** | **False** | **True** |
| -------------------------------- | :-------: | :------: |
| **False**                        |    293    |    59    |
| **True**                         |     3     |     8    |

Modelo LGBM

| **Fold** | **Accuracy** |   **AUC**  | **Recall** |  **Prec.** |   **F1**   |  **Kappa** |   **MCC**   |
| :------: | :----------: | :--------: | :--------: | :--------: | :--------: | :--------: | :---------: |
|     0    |    0.3696    |   0.3298   |   0.6500   |   0.3714   |   0.4727   |   -0.1805  |   -0.2280   |
|     1    |    0.5870    |   0.6163   |   0.7000   |   0.5185   |   0.5957   |   0.1922   |    0.2014   |
|     2    |    0.5000    |   0.5029   |   0.5500   |   0.4400   |   0.4889   |   0.0112   |    0.0115   |
| **Mean** |  **0.4855**  | **0.4830** | **0.6333** | **0.4433** | **0.5191** | **0.0076** | **-0.0050** |
|  **Std** |    0.0893    |   0.1178   |   0.0624   |   0.0601   |   0.0546   |   0.1522   |    0.1757   |

**Considerando thresholds acima de 0**

| **True Class \ Predicted Class** | **False** | **True** |
| -------------------------------- | :-------: | :------: |
| **False**                        |    329    |    23    |
| **True**                         |     3     |     8    |

| **Fold** | **Accuracy** |   **AUC**  | **Recall** |  **Prec.** |   **F1**   |  **Kappa** |   **MCC**  |
| :------: | :----------: | :--------: | :--------: | :--------: | :--------: | :--------: | :--------: |
|     0    |    0.7857    |   0.9123   |   0.5000   |   0.8889   |   0.6400   |   0.5039   |   0.5462   |
|     1    |    0.7381    |   0.7981   |   0.6875   |   0.6471   |   0.6667   |   0.4513   |   0.4519   |
|     2    |    0.4878    |   0.5128   |   0.6000   |   0.3750   |   0.4615   |   0.0205   |   0.0226   |
| **Mean** |  **0.6705**  | **0.7411** | **0.5958** | **0.6370** | **0.5894** | **0.3252** | **0.3402** |
|  **Std** |    0.1307    |   0.1680   |   0.0766   |   0.2099   |   0.0911   |   0.2166   |   0.2279   |



<!-- #endregion -->

```python id="yoBKHAQ8UJiH"
df_test = df_tc_enchentes_cut[df_tc_enchentes_cut['dt'].dt.year >= 2023]
df_train = df_tc_enchentes_cut[df_tc_enchentes_cut['dt'].dt.year < 2023]
```

```python id="bJ-r376sUJiL"
df_train_false = df_train[df_train.enchente == False]
df_train_true = df_train[df_train.enchente == True]
```

```python colab={"base_uri": "https://localhost:8080/", "height": 524} id="dnAdYiktUJiM" outputId="70193fdb-145f-4ff0-dbfc-397e5845b065"
# prompt: for df_train_false clusterize the dataset and grab 20 random samples from each cluster to add to df_train_resampled, that has all the random picked False data and all the rows where enchente is True. If there is a way to decide automatically the number of clusters, do it

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans

# Determine optimal number of clusters using Elbow method
inertia = []
for i in range(1, 11):
    kmeans = KMeans(n_clusters=i, random_state=42)
    kmeans.fit(df_train_false.drop(columns=['dt', 'enchente']))
    inertia.append(kmeans.inertia_)

# Plot the elbow method
plt.plot(range(1, 11), inertia, marker='o')
plt.title('Elbow Method for Optimal k')
plt.xlabel('Number of clusters')
plt.ylabel('Inertia')
plt.show()

```

```python id="lNHiJ9ePUJiN"
# Choose the optimal number of clusters (e.g., based on the elbow point)
optimal_k = 4 # Replace with your choice based on the elbow method plot

# Apply KMeans clustering with the optimal k
kmeans = KMeans(n_clusters=optimal_k, random_state=42)
kmeans.fit(df_train_false.drop(columns=['dt', 'enchente']))
df_train_false['cluster'] = kmeans.labels_

df_train_resampled = df_train[df_train.enchente == True].copy()

# Grab 20 random samples from each cluster
for cluster in range(optimal_k):
    cluster_samples = df_train_false[df_train_false['cluster'] == cluster]
    samples_to_add = cluster_samples.sample(n=min(20, len(cluster_samples)), random_state=42)
    df_train_resampled = pd.concat([df_train_resampled, samples_to_add])

# Remove the cluster column
df_train_resampled = df_train_resampled.drop(columns=['cluster'], errors='ignore')
```

```python colab={"base_uri": "https://localhost:8080/", "height": 178} id="-GCybx-MUJiN" outputId="523cb0f5-f6a9-420d-a3ba-e661c9822b28"
df_train_resampled.enchente.value_counts()
```

```python id="gxCfFykwUJiO"
X = df_train_resampled.drop(columns=["dt"])
X_test = df_test.drop(columns=["dt"])
```

```python colab={"base_uri": "https://localhost:8080/", "height": 600} id="mLsZLb4NUJiO" outputId="a3cda07d-8afa-42b2-c1e1-86c6318fc2ae"
setup(data=X, target="enchente", session_id=123, fix_imbalance=False, fold=3, imputation_type=None, test_data=X_test)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 520, "referenced_widgets": ["76f1cd443989466ba22a4210c891f4df", "9ede62b8c8344aec960f7a981f02bf36", "09ddedbb4865456d8ba265870e1ac9bd", "1f321b2a339c4441bd28eae169c835c8", "6b5fff65bb7d4f08ab448f08e7308877", "9ac128e177114afa8bca595b887ba94c", "f8803d6145ce4ff590884e33317c325f", "a5ef62e3061f415b8eb5d3bf33f6d19f", "181bbe4d0ae94d59a4467ba891e35cb0", "60e5c2e939f94bc487061ae2ee37a2e0", "a648a27ae5f1483b9653ed58ee2f30e5"]} id="7TlTndfaUJiP" outputId="e1430c14-99a9-4739-87fd-508ce225353c"
best_model = compare_models(n_select=1, sort="F1")
```

```python colab={"base_uri": "https://localhost:8080/", "height": 387, "referenced_widgets": ["c4b520bed1f84e1aad986b0aee248918", "4a30e0452e5f4790bd1592fa0bcfcc32", "84c66c9b37d0481d85b4bc8bc24725b6", "c9422bbd00aa4820910d06a01f6ad146", "e65501a10f014bf9bd348480ec35eb89", "0f6a50cf20144261aa2b4fd095cab078", "e548bc9b45144427a1921b8fbb033566", "38f618827c5043e78ccdc4b31b699ee8", "1dc0dfe5f9f240b098083abb8ee737b7", "0ac303bd98534c00a11ec233ac3e7867", "1f1fe0b13b8b4bfd94a24aa84aa0b24a"]} id="isS4muQWUJiP" outputId="174ec598-a470-43f8-e6e4-00d2cf810430"
create_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 666, "referenced_widgets": ["ad23dd8aec014046b3b0e434529a2c77", "06955ad956c34fb599840ec90a6ff777", "8266ea0afc1c48a3b25b6fc5f2ea0f1b", "122b36bf8c4b4df09f34334ff6aa0b8b", "e6ea8faec385455a922614b418d51efb", "039ac095a14846a9b712a7d1a17e5c74", "77af41247c064839a772b92ae07854b1"]} id="x9U9-7dHUJiP" outputId="d45bfa8b-487f-443a-d75c-7712276d790b"
evaluate_model(best_model)
```

<!-- #region id="a7VWe4hMIX4G" -->
# Testa undersampling c/ k alto

* Modelo TAM Central
* Valor de k alto -> 40?

<!-- #endregion -->

```python colab={"base_uri": "https://localhost:8080/"} id="Rz7_TjsmLVk7" outputId="035bf518-5fb9-4879-8d6f-53b0b02b6282"
df_test = df_tc_enchentes_cut[df_tc_enchentes_cut['dt'].dt.year >= 2023].copy()
df_train = df_tc_enchentes_cut[df_tc_enchentes_cut['dt'].dt.year < 2023].copy()

df_train_resampled = cluster_undersample(df_train, target_column='enchente', resample_strength=20, samples_per_cluster=2)

print("\nResampled training data value counts:")
print(df_train_resampled['enchente'].value_counts())
```

```python id="jP9WGs46KBJr"
X = df_train_resampled.drop(columns=["dt"])
X_test = df_test.drop(columns=["dt"])
```

```python colab={"base_uri": "https://localhost:8080/", "height": 600} id="FEMk7CAXKBJr" outputId="279185fb-9c5b-42c3-dc94-7cf806b06cf2"
setup(data=X, target="enchente", session_id=123, fix_imbalance=False, fold=3, imputation_type=None, test_data=X_test)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 520, "referenced_widgets": ["ef5be0ba72d442708fd4f302131805e4", "07fc9c98e565463c8a572a7e40f3003b", "dbc1c937d3fb4ad989a14422e29de533", "1971f361d13b4825b95829d3c17e35f6", "b4c05e733822464c9403c625bbd80641", "87c99d6f6333496c9541980126de77b9", "9b372c9eaea84901b3284c9c35e6471c", "6be698665df64d25a1b7da3e78d0e477", "f816f866db314cfeafcbec71ae3a939e", "069e13e51bee43038db9172190e81d5f", "eeb4cccc1f46443c9e79c07ee823763a"]} id="MxPriBFPKBJr" outputId="f7a0fbb0-a106-4104-f741-1f7e3a54a1cc"
best_model = compare_models(n_select=1, sort="F1")
```

```python colab={"base_uri": "https://localhost:8080/", "height": 335, "referenced_widgets": ["7eb7364408f946debcf10dd915ddd0a8", "f402e4f103634e51b0d9d889100cde2a", "ab26b7c11040474da955198d0fde7ede", "3a965ed51c4841e5aae5c2bfb79d3753", "663f4e51d255498387596b3711185f1b", "76ee33cedcff490fbb6e6c545006b1a9", "6ff4e5750ace457a9f7c4c73ff5ab7ae", "f152d03afb584ce3bfaf97325704ce0a", "2ab85122547947fbb7bb270d79cc5606", "2bc70f120c3946938352b7b929b3009c", "b656bf6a394448d9a352b1957076fe4d"]} id="DZcxpXRcKBJs" outputId="97df4e92-41bf-4b66-b9ee-ec8279f6c8c3"
create_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 487} id="37FOHBGaNvCZ" outputId="e1b873b3-c71b-4e47-fcbe-fa162898d921"
predict_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 242} id="IDqXZSRVYxFW" outputId="b9582bb7-d0c3-48de-9dd1-a6696574b648"
# prompt: predict model with best model and show me the filtered resulting df with only the false negatives

# Make predictions on the test data using the best model
predictions = predict_model(best_model, data=X_test)

# Filter the predictions DataFrame to show only False Negatives
# False Negatives are instances where the true value was True (1) but the model predicted False (0)
false_negatives_df = predictions[(predictions['enchente'] == True) & (predictions['prediction_label'] == 0)].copy()

# Print or display the filtered DataFrame
print("\nFalse Negatives:")
false_negatives_df
```

```python colab={"base_uri": "https://localhost:8080/", "height": 179} id="YwrLaoK1ZFlG" outputId="b76f0378-e9f6-4355-f143-cda17d0f85d1"
# prompt: now with the same predictions grab 3 random true positives

# Filter the predictions DataFrame to show only True Positives
# True Positives are instances where the true value was True (1) and the model predicted True (1)
true_positives_df = predictions[(predictions['enchente'] == True) & (predictions['prediction_label'] == 1)].copy()

# Randomly sample 3 true positives
random_true_positives = true_positives_df.sample(n=min(3, len(true_positives_df)))

# Print or display the sampled true positives
print("\n3 Random True Positives:")
random_true_positives
```

```python id="stc7UmH1YSPW"

```

```python colab={"base_uri": "https://localhost:8080/", "height": 666, "referenced_widgets": ["90f4ad9c767d4184a0583560c8bbb099", "ad95e9f9c89246788dc08a592c4210ba", "1f162091330d4ff593770a290ac8737c", "ed4e544e1b1543919538abd18686b6cd", "f7027ff9da3e4ae28dff6c8a11cea78c", "318ddf68be6a4d8eb75fe75166d3c22c", "84b0e1d6bc7944ad8c8ba6dcc548c2ab"]} id="xrkfCYiAKBJs" outputId="d8207a20-e7e3-4554-c244-3872c6880da5"
evaluate_model(best_model)
```

<!-- #region id="pyjkPFMHQU97" -->
# Testa novo agregado de máximo

* Em vez de pegar apenas o valor máximo, pega a média entre os 2 ou 3 maiores valores entre as estações.
* Testa com modelo TC e undersampling c/ k alto
<!-- #endregion -->

```python id="xlb3ZGhGQzsP"
def agg_avg_top_n(n):
  """
  Creates a function to calculate the average of the top n values in a pandas Series.
  This is intended for use with the pandas .agg() method.

  Args:
    n (int): The number of top values to consider for the average.

  Returns:
    function: A function that takes a pandas Series and returns the average of its top n values.
  """
  def avg_top_n(series):
    if series.empty:
      return np.nan
    # Sort in descending order and take the top n values
    top_values = series.nlargest(n)
    return top_values.mean()
  # Give the function a more descriptive name for clarity when used in agg
  avg_top_n.__name__ = f'avg_top_{n}'
  return avg_top_n
```

```python id="FZhNDPRdVDiZ"
tamanduatei_central = [
    "Cidade São Jorge",
    "Jardim Ipanema",
    "Paraíso",
    "Parque das Nações",
    "Santa Terezinha",
    "Vila Bastos",
    "Vila João Ramalho",
    "Vila Suiça",
    "Vila Vitória",
]
```

```python id="aygff3olVDic"
df_dm_tam_central = df_daily_metrics[df_daily_metrics["nomeEstacao"].isin(tamanduatei_central)].copy()
```

```python id="hr_xGCptQxj7"
df_dm_tc_grouped = df_dm_tam_central.groupby(["ano", "mes", "dia"]).agg({
    "chuva_total": "sum",
    "chuva_max_1h": agg_avg_top_n(3),
    "chuva_max_3h": agg_avg_top_n(3),
    "horas_com_chuva": agg_avg_top_n(3),
    "horas_intensas_10mm": agg_avg_top_n(3),}).reset_index()
```

```python id="iszdA-EuQxj8"
df_dm_tc_dt = df_dm_tc_grouped.copy()
df_dm_tc_dt['dt'] = pd.to_datetime(df_dm_tc_dt.apply(lambda row: f"{int(row['dia']):02}/{int(row['mes']):02}/{int(row['ano'])}", axis=1), dayfirst=True)
df_dm_tc_dt.drop(columns=["ano", "mes", "dia"], inplace=True)
```

```python id="AEawGsroQxj9"
df_dm_tc_sazonal = df_dm_tc_dt[~df_dm_tc_dt["dt"].dt.month.between(5, 10)].copy()
```

```python id="ej67kEIFWIM9"
df_tc_enchentes = df_dm_tc_sazonal.copy()
df_tc_enchentes['enchente'] = df_tc_enchentes['dt'].isin(df_enchentes_verificados['dt'])
```

```python colab={"base_uri": "https://localhost:8080/"} id="dZwNeOOsVzkx" outputId="c42f20ff-f877-438f-fbab-2e40e6bcb7be"
# Define the thresholds for each feature
thresholds = {
    'chuva_total': 10,
    'chuva_max_1h': 2,
    'chuva_max_3h': 6,
    'horas_com_chuva': 2
}

# Create a copy of the DataFrame to avoid modifying the original
df_tc_enchentes_cut = df_tc_enchentes.copy()

# Initialize a counter for the number of labels changed
labels_changed = 0

# Iterate through the DataFrame
for index, row in df_tc_enchentes.iterrows():
    # Check if 'enchente' is True
    if row['enchente']:
        # Check if any of the specified features are below the threshold
        for feature, threshold in thresholds.items():
            if row[feature] <= threshold:
                # Change the 'enchente' label to False
                df_tc_enchentes_cut.loc[index, 'enchente'] = False
                labels_changed += 1
                break  # Exit the inner loop once a threshold is met

# Print the number of labels changed
print(f"{labels_changed} labels were changed.")

```

```python colab={"base_uri": "https://localhost:8080/"} id="vdukBKryVjxO" outputId="ec8c2502-6405-4446-dd75-a5fc9d989e04"
df_test = df_tc_enchentes_cut[df_tc_enchentes_cut['dt'].dt.year >= 2023].copy()
df_train = df_tc_enchentes_cut[df_tc_enchentes_cut['dt'].dt.year < 2023].copy()

df_train_resampled = cluster_undersample(df_train, target_column='enchente', resample_strength=20, samples_per_cluster=2)

print("\nResampled training data value counts:")
print(df_train_resampled['enchente'].value_counts())
```

```python id="VkA3mDY2VjxQ"
X = df_train_resampled.drop(columns=["dt"])
X_test = df_test.drop(columns=["dt"])
```

```python colab={"base_uri": "https://localhost:8080/", "height": 600} id="A_rn-Q6dVjxR" outputId="de0aacc4-6341-435a-86e1-a1942d6770ae"
setup(data=X, target="enchente", session_id=123, fix_imbalance=False, fold=3, imputation_type=None, test_data=X_test)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 520, "referenced_widgets": ["0a7c5cc521af4eee92cceb339120eb28", "1037d42df6794a33a02fbfef576c1b38", "85eb0bbc66464e7b9022ad3ea6f322b1", "da036ee3825b4bf7a30ecbe4c0b2577d", "2e65f24756864be5bd5e70c7324e4ff5", "cb17edf7122f454b9bc37d09bae9f11f", "defa71247cd2488dbe479ce17ddce706", "bada7bb79f284b78954d3ea87e51a42c", "996d7e6e54b649c5855d5dc58463fd85", "c273373fc06f450284a25563724caf03", "82c20224898c46ebbd16731163f1865c"]} id="PnUYAOXLVjxR" outputId="bea659f4-3f25-4854-ea3d-4d17df7992c7"
best_model = compare_models(n_select=1, sort="F1")
```

```python colab={"base_uri": "https://localhost:8080/", "height": 387, "referenced_widgets": ["90780999e27a4947a0da9442beb28667", "a4cb77c6889c4df1ba440a9b85612f26", "8594d4bdf02f406f81450c02a767387d", "b933dc4b1bbb486f96b4ea939167d041", "5ac50eed709e45ae8e1a7f1cfd5f1fc0", "e08e2722a100490494c813152a2ee4a8", "627f605c46b944e9b0609d8d5d8cfd59", "94f36c989b694af29bd729af0087a3ab", "0d1585f81716423ca0c5f09aa9851ce9", "eb2fd69d1ae04525b09bb91de97009ed", "95345272f349476bab15b51b98077c55"]} id="EoxsFIq-VjxS" outputId="163d2fa4-789e-4ca2-ba56-02d97f83a0e8"
create_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 487} id="gvk4lGQ9VjxS" outputId="1d5e457b-0b36-4613-bf76-df7f886918f3"
predict_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 666, "referenced_widgets": ["b0eb7ed08aa549439b4fae7914187659", "c056e14147bd43b995b01a11b68c2a39", "f03eb07b103645fc81717a8ea929f05f", "af9c5fa4cc064d7095769235b5f6c933", "7fc699d850b34457803927ed43105a3c", "7f4beab8a3254e8a938b5afa06f9f42e", "15f60c3d2e644ed68264a4b0f253cd8e"]} id="NIDFcbnKVjxS" outputId="2622fd0b-0639-4e24-fed8-0700c35baeb0"
evaluate_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/"} id="1SY6fPkCmCaz" outputId="f200144d-f3e9-48d0-a52f-3ddde9aef8e1"
df_enchentes_verificados.ano.unique()
```

```python colab={"base_uri": "https://localhost:8080/"} id="QIQz7iesm18L" outputId="185156d7-92e8-4055-f3a4-030af3bf1a2c"
df_enchentes_verificados.shape
```

```python colab={"base_uri": "https://localhost:8080/"} id="B4Gi7MQhm8rh" outputId="1ee908c8-a0bb-4182-e250-f34cc6eecb99"
df_enchentes_verificados.query("ano >= 2023").shape
```

```python colab={"base_uri": "https://localhost:8080/", "height": 206} id="GW_SDPm2nQeg" outputId="9efef694-d991-408c-a12d-c1d0c3c9c9b5"
df_dm_enchentes.head()
```

```python colab={"base_uri": "https://localhost:8080/", "height": 335} id="aVfeItPSnbR7" outputId="6eaa8bd4-7721-4ccc-f393-25d47a0f53c2"
df_dm_enchentes.query('chuva_total > 3').chuva_total.describe()
```

```python colab={"base_uri": "https://localhost:8080/"} id="z4vIfuz9nl3x" outputId="97fa3b1c-7863-46aa-e053-fcd73d4ee406"
df_dm_enchentes.query('chuva_total > 15').shape
```

<!-- #region id="3_UpiglQpF9K" -->
Definição de chuva moderada: entre 2.5 10 mm/h
chuva fraca: < 2.5
chuva forte: 10 - 50
muito forte / violenta : 50+
<!-- #endregion -->

```python colab={"base_uri": "https://localhost:8080/", "height": 178} id="km9xzQk_oiAB" outputId="f1d2a3b9-eb10-4481-d51f-d6e599f53864"
df_dm_enchentes.query('chuva_max_1h > 50').enchente.value_counts()
```

<!-- #region id="xMg7Mx-cQS1-" -->
# Valida enchente por endereço de chamado
<!-- #endregion -->

```python id="7QGBEaQpGZdg"
import unicodedata

def strip_accents(s):
    """
    Remove accent marks and diacritics from a string using Unicode normalization.

    This function decomposes the input string using NFD Unicode normalization and
    removes all combining character markers (accent/diacritic marks) to return
    a simplified ASCII-friendly version of the text.

    Parameters:
    ----------
    s : str
        The input string containing potential accented characters or diacritics.

    Returns:
    -------
    str
        The processed string with accent marks removed while preserving original characters.
    """
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                  if unicodedata.category(c) != 'Mn')


def rename_neighborhood_list(name_list):
    """
    Standardize neighborhood names by converting to uppercase, replacing common terms,
    and removing accents.

    This function processes a list of neighborhood names by:
    1. Converting all characters to uppercase
    2. Replacing common prefixes with abbreviations (VILA → VL, JARDIM → JD, etc.)
    3. Stripping accent marks using the strip_accents utility
    4. Modifies AND returns the input list object (operates in-place)

    Parameters:
    ----------
    name_list : list[str]
        A list of neighborhood name strings to be standardized in-place.

    Returns:
    -------
    list[str]
        The modified input list containing standardized neighborhood names. Common
        replacements include:
        - "VILA" becomes "VL"
        - "JARDIM" becomes "JD"
        - "PARQUE" becomes "PQ"

    Note:
    -----
    This function modifies the original list object while returning it. Consider making
    a copy if the original list needs to be preserved.
    """
    for i, name in enumerate(name_list):
        name_list[i] = strip_accents(name.upper().replace("VILA", "VL").replace("JARDIM", "JD").replace("PARQUE", "PQ"))
    return name_list

```

```python id="USFGKnPMG-Zz"
def prepare_basin_df(basin_list):
  df_chamados_neigh = df_chamados.copy()
  df_chamados_neigh['bairro'] = df_chamados_neigh['end'].str.extract(r'-\s*([A-Z\s]+)$')
  df_chamados_basin = df_chamados_neigh[df_chamados_neigh['bairro'].isin(basin_list)].drop(columns=['bairro', 'end'])
  return df_chamados_basin.copy()
```

```python colab={"base_uri": "https://localhost:8080/"} id="R0aOg2JJQgRD" outputId="82e668b0-11f1-49d9-ef1e-1f0e9133a064"
file_chamados = 'df_chamados_defciv.csv'
grab_from_gdrive('1Fa5TOO-hXAT4l7-IyA51Kswjdxn7WoQD', file_chamados)
df_chamados = pd.read_csv(file_chamados)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 424} id="hvPn__CpSvFG" outputId="996f5454-4867-443c-fccd-33c48df9bda0"
df_chamados.rename(
    columns={
        "ENDEREÇO": "end",
        "DATA": "dt",
        "SERVIÇO": "serv",
        "ENCAMINHAMENTO": "enc",
        "SOLICITANTE": "solic"
        }
    )
```

```python id="OYbDN6ISIVne"
tamanduatei_central = ["Campestre", "Santa Maria", "Jardim", "Vila Alpina",
"Vila Guiomar", "Vila Alice", "Vila Bastos", "Jardim Bela Vista", "Centro",
"Casa Branca", "Vila Gilda", "Paraíso", "Vila Assunção", "Vila Alzira",
"Silveira", "Vila Linda", "Vila Helena", "Jardim do Estádio",
"Jardim Santa Cristina", "Jardim Guarará", "Sítio dos Vianas",
"Jardim Cipreste", "Jardim Irene", "Vila João Ramalho", "Jardim Vila Rica",
"Cata Preta", "Jardim Santo André CDHU", "Jardim Santo André CDHU",
"Vila Luzita", "Jardim Telles de Menezes", "Vila Suiça", "Condomínio Maracanã",
"Vila Lutécia", "Vila Tibiriça", "Vila Vitória", "Jardim Ipanema",
"Vila Guaraciaba", "Vila Progresso", "Parque Gerassi", "Cidade São Jorge",
"Centreville", "Vila Guarani", "Vila Humaitá", "Parque Marajoara",
"Vila Homero Thon", "Vila América", "Vila Pires", "Silveira", "Vila Alzira",
"Novo Homero Thon", "Várzea do Tamanduateí", "Jardim Alzira Franco",
"Parque Jaçatuba", "Vila Curuça", "Bangú", "Parque das Nações",
"Santa Terezinha", "Vila Francisco Matarazzo", "Jardim Santo Antônio",
"Vila Camilópolis", "Vila Metalúrgica"]

tamanduatei_central_renamed = rename_neighborhood_list(tamanduatei_central)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 561} id="wKQM3TdcK4oj" outputId="3b939d3b-d6b2-4bb0-be89-0bc4121c63f2"
df_chamados_tamanduatei_central = prepare_basin_df(tamanduatei_central_renamed)
df_chamados_tamanduatei_central_unique = df_chamados_tamanduatei_central.drop_duplicates(subset=['dt']).reset_index(drop=True)
```

<!-- #region id="5fQhgyhxpfdA" -->
# Testa modelo para pancadas de chuva
<!-- #endregion -->

```python colab={"base_uri": "https://localhost:8080/", "height": 178} id="vhXnasPVp8Vm" outputId="6f36d022-ba94-426e-be78-3e8901e695f6"
df_tc_enchentes_cut_max = df_tc_enchentes.query('chuva_max_1h > 10')
```

```python colab={"base_uri": "https://localhost:8080/"} id="0Bc5g3_jrwZ2" outputId="35856c9d-e26b-44cf-8adb-cbe36dd6e11c"
df_test = df_tc_enchentes_cut[df_tc_enchentes_cut['dt'].dt.year >= 2022].copy()
df_train = df_tc_enchentes_cut[df_tc_enchentes_cut['dt'].dt.year < 2022].copy()

df_train_resampled = cluster_undersample(df_train, target_column='enchente', resample_strength=20, samples_per_cluster=2)

print("\nResampled training data value counts:")
print(df_train_resampled['enchente'].value_counts())
```

```python colab={"base_uri": "https://localhost:8080/", "height": 178} id="mQz5NQgguIIr" outputId="e204cb1a-7a12-4893-8ae4-895574dc560f"
df_test.enchente.value_counts()
```

```python id="7eQ30j4vrwZ7"
X = df_train_resampled.drop(columns=["dt"])
X_test = df_test.drop(columns=["dt"])
```

```python colab={"base_uri": "https://localhost:8080/", "height": 600} id="g1CYH4r9rwZ9" outputId="5bd114ec-13d9-4465-f456-42b68dd14086"
setup(data=X, target="enchente", session_id=123, fix_imbalance=False, fold=3, imputation_type=None, test_data=X_test)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 520, "referenced_widgets": ["c5c81fcb98d14ecd933610234f7f12f9", "d625b2d0bcc54b3fa6c76585e62747de", "c0c976dff5b44a4289a477919ed633db", "aa3bda6492e7464f8d397f1e0b5648bb", "ad4060c463dd4695a74133f17418ef1d", "2dac1373671046c09607179dd6a82c0b", "3bbffc860f134ce4939b1232e5905c17", "4691abe93e0740bd9f1d0d165b62961b", "c495c7dabc3144679ec53a97d3d018d4", "3d11e41abde840eabdea6b03307333e4", "d160cc6ff3dd41f492ee1ed862891cd9"]} id="jxyciq6DrwZ_" outputId="02a7f47d-b575-43d7-d994-d6bdd58c9a72"
best_model = compare_models(n_select=1, sort="Prec.")
```

```python colab={"base_uri": "https://localhost:8080/", "height": 388, "referenced_widgets": ["d294da1be46a4b119f2f09a4c4829216", "bf18608de6924b4caede77d82761fb49", "56857cda92e84254b86b8d18ce4bd4b8", "4626375d78b94d008f50089ba6cd03bd", "9c88469393fd410bb1f8d5a2d5c4f76a", "610abcbefd8b4444bbad210933b5d1d3", "0bc5492594394f2d876c042149c36bc7", "dafcb2f469944f20967f5569471b4b7f", "5e12c2173cb64475a64a320ce1c66778", "03995eb6739a42b0810028a87ac21ef1", "3236baec1feb42baa770a1d71158c1e2"]} id="I2eNl2WDrwaA" outputId="9786b007-65e1-4abe-ae10-3e799c52ac75"
create_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 488} id="L-CqfX7wrwaB" outputId="bd9a6d73-cc04-4e0f-c34f-cac2e417a3ac"
predict_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 665, "referenced_widgets": ["2e620e7091da47d2b0ffb696dcf36cf7", "1c0a94f2d7bd4c159ae70893e2c1fdea", "a97b90aac33842e5a4ab9663bff084b6", "836a3783d8284d08beda68d7ea40e566", "c4a135161a984c989e67084f8f33b9a7", "cde93c7c137447ac8e3f78f79c118a24", "a715b01780664343ab7797fe613d1cda"]} id="l8ByAMCHuxRs" outputId="403b4f4e-d5e6-4301-8863-db79e72ed39a"
evaluate_model(best_model)
```

```python colab={"base_uri": "https://localhost:8080/", "height": 242} id="fdcD21rerwaC" outputId="b9582bb7-d0c3-48de-9dd1-a6696574b648"
# prompt: predict model with best model and show me the filtered resulting df with only the false negatives

# Make predictions on the test data using the best model
predictions = predict_model(best_model, data=X_test)

# Filter the predictions DataFrame to show only False Negatives
# False Negatives are instances where the true value was True (1) but the model predicted False (0)
false_negatives_df = predictions[(predictions['enchente'] == True) & (predictions['prediction_label'] == 0)].copy()

# Print or display the filtered DataFrame
print("\nFalse Negatives:")
false_negatives_df
```

```python colab={"base_uri": "https://localhost:8080/", "height": 179} id="sPH0oR25rwaE" outputId="b76f0378-e9f6-4355-f143-cda17d0f85d1"
# prompt: now with the same predictions grab 3 random true positives

# Filter the predictions DataFrame to show only True Positives
# True Positives are instances where the true value was True (1) and the model predicted True (1)
true_positives_df = predictions[(predictions['enchente'] == True) & (predictions['prediction_label'] == 1)].copy()

# Randomly sample 3 true positives
random_true_positives = true_positives_df.sample(n=min(3, len(true_positives_df)))

# Print or display the sampled true positives
print("\n3 Random True Positives:")
random_true_positives
```

```python colab={"base_uri": "https://localhost:8080/", "height": 666, "referenced_widgets": ["90f4ad9c767d4184a0583560c8bbb099", "ad95e9f9c89246788dc08a592c4210ba", "1f162091330d4ff593770a290ac8737c", "ed4e544e1b1543919538abd18686b6cd", "f7027ff9da3e4ae28dff6c8a11cea78c", "318ddf68be6a4d8eb75fe75166d3c22c", "84b0e1d6bc7944ad8c8ba6dcc548c2ab"]} id="BFtCcJEXrwaF" outputId="d8207a20-e7e3-4554-c244-3872c6880da5"
evaluate_model(best_model)
```
