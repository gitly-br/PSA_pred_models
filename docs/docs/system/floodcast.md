---
title: Floodcast
slug: /floodcast
sidebar_position: 4
---

# Módulo Floodcast (Motor de Inferência)

O `floodcast` é o motor de inferência do Sistema de Predição de Alagamentos (PSA). Este módulo é uma pipeline de Machine Learning que utiliza dados de previsão do tempo para gerar as previsões de alagamento. Ele foi construído com um foco em reprodutibilidade e interpretabilidade dos modelos.

## 1. Arquitetura da Pipeline de Inferência

O processo de inferência é orquestrado pelo `main.py` e segue uma sequência de passos bem definida para garantir a consistência e a confiabilidade das previsões.

### 1.1. `main.py`

O ponto de entrada do módulo. Ele coordena todo o fluxo de trabalho da pipeline:

1.  **Carregamento de Configurações:** Busca as configurações de todos os modelos de previsão armazenados no MongoDB.
2.  **Verificação de Inferência:** Verifica se uma previsão para a data alvo já foi gerada, evitando reprocessamento desnecessário.
3.  **Carregamento de Dados:** Utiliza o `ForecastLoader` para carregar os dados de previsão do tempo (coletados pelo módulo `harvest`) que servirão de entrada para os modelos.
4.  **Execução das Previsões:** Aciona o `ModelPredictor` para executar cada um dos modelos de Machine Learning.
5.  **Armazenamento dos Resultados:** Usa o `InferenceWriter` para processar os resultados, gerar uma explicação para a previsão e salvar o objeto de inferência final no MongoDB.

### 1.2. `model_predictor.py`

O coração do motor de inferência. Para cada modelo configurado, ele executa os seguintes passos:

1.  **Download dos Artefatos:** Baixa o modelo de Machine Learning pré-treinado (um arquivo `.joblib` contendo uma pipeline do Scikit-learn) e um explicador SHAP do Google Drive.
2.  **Predição:** Carrega a pipeline e a utiliza para fazer a predição com base nos dados de previsão do tempo.
3.  **Interpretabilidade:** Utiliza o explicador SHAP para identificar quais variáveis (features) tiveram maior impacto na decisão do modelo.
4.  **Formatação da Saída:** Empacota o resultado da predição, a explicação do SHAP e outros metadados em um objeto Python.

### 1.3. `inference_writer.py`

Este módulo é responsável por consolidar as previsões de todos os modelos em um único objeto de inferência. Ele calcula a probabilidade de alagamento para cada região, gera uma explicação em linguagem natural com base nos valores SHAP e escreve o resultado final no banco de dados.

### 1.4. `custom_transformers.py`

Este arquivo define transformadores personalizados para as pipelines do Scikit-learn. O `WindowAgg` é um exemplo notável, que agrega dados de séries temporais em janelas (ex: a cada 6 horas) para criar features como a média, o máximo e a soma da precipitação, que são então utilizadas pelos modelos.

## 2. Tecnologias e Conceitos

- **Scikit-learn:** Utilizado para a criação e execução das pipelines de Machine Learning.
- **SHAP (SHapley Additive exPlanations):** Uma biblioteca para a interpretabilidade de modelos de Machine Learning, que ajuda a entender o porquê de uma determinada previsão ter sido feita.
- **Joblib:** Para a serialização e desserialização dos modelos e pipelines treinados.
- **MongoDB:** Utilizado para armazenar as configurações dos modelos e os resultados das inferências.
- **Google Drive:** Utilizado como um repositório para os artefatos dos modelos treinados (arquivos `.joblib`).