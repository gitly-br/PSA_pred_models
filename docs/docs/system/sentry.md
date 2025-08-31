---
title: Sentry
slug: /sentry
sidebar_position: 3
---

# Módulo Sentry (Backend API)

O módulo `sentry` é a API de backend do Sistema de Predição de Alagamentos (PSA). Desenvolvido com o framework [Sanic](https://sanic.dev/), ele atua como um microserviço escalável e configurável, responsável por servir os dados necessários para o frontend em Streamlit.

## 1. Arquitetura e Estrutura

A aplicação é estruturada de forma modular, utilizando `Blueprints` do Sanic para organizar as diferentes rotas da API.

### 1.1. `run.py`

Este é o ponto de entrada da aplicação. Suas principais funções são:

- **Inicialização:** Interpreta os argumentos de linha de comando para definir o ambiente de execução (desenvolvimento, produção ou local).
- **Carregamento de Configurações:** Carrega as configurações da aplicação a partir de um banco de dados MongoDB central, o que permite uma gestão centralizada das configurações para diferentes ambientes.
- **Criação da Aplicação:** Utiliza a função `create_app` como uma fábrica para instanciar a aplicação Sanic.
- **Execução do Servidor:** Inicia o servidor Sanic, configurando o número de `workers` com base nos recursos da máquina para otimizar o desempenho.

### 1.2. `app/common/app.py`

Este arquivo contém a função `create_app`, que é a fábrica responsável por criar e configurar o objeto da aplicação Sanic. Suas responsabilidades incluem:

- **Configuração do Sanic:** Aplica diversas configurações à aplicação, como CORS, timeouts, e endpoints de monitoramento de saúde (`health check`).
- **Registro de Blueprints:** Registra os `Blueprints` que definem as rotas da API. Ele distingue entre `Blueprints` comuns (reutilizáveis em outras aplicações) e os `Blueprints` específicos da aplicação.
- **Gestão de Ciclo de Vida:** Configura eventos que ocorrem antes do início e após o término do servidor, como a inicialização de um cliente HTTP (`httpx`) para comunicação com outros serviços.

### 1.3. `app/sanic_blueprints/blueprint_register.py`

Este arquivo centraliza o registro de todos os `Blueprints` específicos da aplicação, que são o coração da funcionalidade da API. Cada `Blueprint` corresponde a um conjunto de rotas relacionadas:

- **`bp_get_dates`:** Provavelmente para obter as datas para as quais existem previsões disponíveis.
- **`bp_home`:** Rota principal, utilizada pela página inicial do frontend.
- **`bp_forecast`:** Fornece os dados de previsão de alagamento.
- **`chamados_pbi_bp`:** Rota relacionada ao dashboard de ocorrências do Power BI.
- **`bp_region`:** Fornece dados para uma região ou bacia hidrográfica específica.
- **`bp_forecast_data`:** Fornece os dados de entrada que foram utilizados para gerar as previsões.

## 2. Tecnologias Utilizadas

- **Sanic:** Framework web assíncrono de alta performance para a construção da API.
- **httpx:** Cliente HTTP assíncrono para a comunicação com outros serviços.
- **MongoDB:** Utilizado como banco de dados central para o armazenamento de configurações.