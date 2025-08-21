---
title: Visão geral do sistema
slug: /system
sidebar_position: 2
---

# Visão geral do sistema

A arquitetura do sistema de predição de alagamentos foi projetada em um modelo de serviços distribuídos e conteinerizados, orquestrados pelo Docker Compose. Esta abordagem desacopla as principais responsabilidades da aplicação em três serviços distintos: `frontend`, `backend` e `mongo`. O serviço `backend`, por sua vez, encapsula a lógica de negócio em três processos Python concorrentes que se comunicam de forma assíncrona através do banco de dados `mongo`, que atua como um barramento de dados central.

A imagem a seguir ilustra a arquitetura do sistema:


### Arquitetura de Serviços

O sistema é dividido nos seguintes serviços Docker:

*   **`mongo`**: Uma instância do MongoDB que atua como o barramento de dados central, armazenando dados meteorológicos, predições e outras informações relevantes.
*   **`frontend`**: Uma aplicação [Streamlit](https://streamlit.io/) que fornece a interface gráfica para o usuário. Ela é responsável por visualizar os dados e as predições, consumindo as informações a partir da API do `backend`.
*   **`backend`**: O núcleo do sistema. É um único contêiner Docker que executa três processos Python distintos, gerenciados por um script `entrypoint.sh`. Essa abordagem permite a separação lógica das responsabilidades, mantendo a simplicidade operacional.

### Módulos do Backend

O serviço `backend` é composto pelos seguintes módulos, que rodam concorrentemente:

#### 1. Sentry (API Server)
*   **Tecnologia:** [Sanic](https://sanic.dev/) (Servidor web assíncrono).
*   **Função:** É o processo principal do contêiner. Atua como uma API REST, expondo os dados processados para o `frontend`. Ele lê as informações diretamente do MongoDB, como as predições geradas pelo *Floodcast* e os dados de regiões, e as serve de forma otimizada.

#### 2. Harvest (Coletor de Dados)
*   **Tecnologia:** Processo Python em loop, utilizando `Typer` para a interface de linha de comando.
*   **Função:** Executa como um serviço em segundo plano. Em intervalos de tempo configuráveis, este módulo realiza chamadas à API externa do [OpenWeather](https://openweathermap.org/), coleta os dados meteorológicos mais recentes e os armazena na coleção apropriada no MongoDB. Ele é a porta de entrada de dados para o sistema.

#### 3. Floodcast (Motor de Predição)
*   **Tecnologia:** Processo Python em loop, utilizando `Typer`.
*   **Função:** Também executa como um serviço em segundo plano. Este módulo monitora o MongoDB por novos dados inseridos pelo *Harvest*. Ao encontrar novos dados, ele os carrega, aplica os modelos de machine learning pré-treinados para gerar as predições de risco de alagamento e, por fim, salva os resultados (inferências) em uma coleção específica no MongoDB.

### Fluxo de Dados

O fluxo de dados no sistema segue um ciclo claro e desacoplado, orquestrado pelo MongoDB:

1.  O **Harvest** coleta dados externos e os insere no MongoDB.
2.  O **Floodcast** lê esses dados brutos, processa-os, gera predições e salva os resultados de volta no MongoDB.
3.  O **Sentry** lê os resultados das predições e os expõe através de sua API.
4.  O **Frontend** consome os dados da API do Sentry e os exibe ao usuário.

Este design garante que cada módulo tenha uma responsabilidade única e que a comunicação entre eles seja assíncrona, aumentando a resiliência e a escalabilidade do sistema.
