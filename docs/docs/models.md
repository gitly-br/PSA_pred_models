---
title: Considerações sobre os modelos
sidebar_position: 4
slug: models
---

# Modelos de Previsão

Este documento técnico descreve o processo de desenvolvimento de um modelo de previsão de enchentes, abordando as etapas de coleta, pré-processamento, feature engineering, modelagem e avaliação.

## 1. Coleta e Preparação dos Dados

O desenvolvimento do modelo utilizou dois principais conjuntos de dados:

*   **Dados Meteorológicos (OpenWeather):** Incluem dados históricos e de previsão (forecasts) de diversas variáveis climáticas, como temperatura, ponto de orvalho, pressão, umidade, velocidade e direção do vento, rajadas de vento, precipitação (acumulada por hora), nebulosidade, convecção e probabilidade de precipitação. Foi realizada a limpeza dos dados, incluindo o tratamento de valores ausentes através de técnicas de imputação (conforme detalhado na Seção 3).
*   **Dados de Chamados:** Contêm registros de ocorrências de enchentes, incluindo informações como endereço e data/hora do chamado.

## 2. Feature Engineering e Agregação de Dados

Para extrair informações relevantes dos dados brutos e prepará-los para a modelagem, foram aplicadas técnicas de feature engineering:

*   **Agregação Temporal:** Os dados meteorológicos horários (históricos e de forecast) foram agregados por dia. Foram utilizadas diferentes estratégias de agregação, incluindo:
    *   Cálculo de métricas estatísticas (média, soma, mínimo, máximo, delta - diferença entre máximo e mínimo) para períodos de 6, 12 ou 24 horas dentro de cada dia.
    *   Criação de features representando a variação de variáveis ao longo de diferentes turnos do dia (manhã, tarde, noite).
*   **Criação da Variável Alvo:** Uma variável binária (`chamado`) foi criada para indicar a ocorrência de pelo menos um chamado de enchente em um determinado dia. Adicionalmente, a contagem de chamados por dia (`counts`) foi incluída para análises mais detalhadas.

## 3. Tratamento de Desbalanceamento e Filtragem de Dados

O dataset apresentava um desbalanceamento significativo, com um número muito maior de dias sem chamados do que com chamados. Para mitigar este problema e melhorar a performance do modelo, foram exploradas diversas estratégias:

*   **Análise de Sazonalidade:** Foi identificada uma forte sazonalidade na ocorrência de chamados, com baixa incidência em determinados meses. Um filtro foi aplicado para incluir apenas os meses com maior frequência de enchentes, reduzindo o tamanho do dataset e diminuindo o desbalanceamento.
*   **Análise da Influência da Precipitação:** A distribuição da precipitação em dias com e sem chamados foi analisada. Cortes nos dados foram aplicados com base em limiares de precipitação para focar em dias com maior probabilidade de ocorrência de enchentes.
*   **Undersampling:** Técnicas de undersampling, como Cluster Centroids, foram aplicadas ao conjunto de treino para equilibrar a proporção entre as classes positiva (com chamado) e negativa (sem chamado). Diferentes proporções de undersampling (ex: 1:1, 1:0.75) foram testadas.
*   **Cortes Iterativos:** Ferramentas de análise de distribuição e simulação de cortes foram desenvolvidas para identificar e aplicar cortes automáticos e manuais nos dados, visando reduzir o número de casos negativos sem eliminar casos positivos de forma significativa.

## 4. Modelagem Preditiva

A tarefa de previsão de enchentes foi tratada como um problema de classificação binária. A biblioteca PyCaret foi utilizada para automatizar o processo de treinamento e comparação de múltiplos modelos de machine learning.

*   **Comparação de Modelos:** Diversos algoritmos de classificação foram avaliados (conforme apresentado nas tabelas de comparação de modelos), selecionando os de melhor desempenho com base em métricas como Acurácia, Recall, Precisão, F1-Score e AUC.
*   **Estratégias de Dados para Treinamento:** Foram comparadas diferentes abordagens quanto à utilização dos dados:
    *   Modelos treinados apenas com dados de forecast.
    *   Modelos treinados apenas com dados históricos.
    *   Modelos treinados com a combinação de dados históricos e de forecast.
*   **Modelos Regionais:** Foram desenvolvidos modelos específicos para diferentes bacias hidrográficas (Meninos, Oratório, Tamanduateí Central, Guarará) utilizando os dados de chamados filtrados pelos bairros pertencentes a cada bacia.

## 5. Avaliação do Modelo

A performance dos modelos foi avaliada utilizando métricas padrão de classificação. Além da avaliação geral no conjunto de teste, foram realizadas análises específicas:

*   **Avaliação por Nível de Precipitação:** A performance dos modelos foi analisada em subconjuntos do conjunto de teste com diferentes níveis de precipitação (ex: acima da mediana, acima do percentil 75, acima do percentil 95), para verificar o desempenho em condições climáticas mais extremas.
*   **Validação Cruzada:** A validação cruzada (com 5 folds) foi utilizada durante o treinamento no PyCaret para obter estimativas mais robustas da performance dos modelos.
*   **Análise de Explicabilidade (SHAP):** A biblioteca SHAP foi empregada para entender a contribuição de cada feature para as previsões individuais do modelo, fornecendo insights sobre a decisão do modelo para um determinado dia.
