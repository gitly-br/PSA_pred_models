---
title: Frontend
slug: /frontend
sidebar_position: 1
---

# Frontend do sistema

O frontend do Sistema de Predição de Alagamentos (PSA) é uma aplicação web
desenvolvida com [Streamlit](https://streamlit.io/), projetada para fornecer
uma interface intuitiva e interativa para visualização das previsões de
alagamento em Santo André.

## 1. Estrutura da Aplicação

A aplicação é dividida em várias páginas, cada uma com uma função específica. A
navegação é gerenciada pelo arquivo principal `app.py`.

### 1.1. `app.py`

Este é o ponto de entrada da aplicação. Suas principais responsabilidades são:

- **Autenticação de Usuário:** Gerencia o login dos usuários.
- **Configuração da Página:** Define o layout geral, título e ícone da aplicação.
- **Navegação:** Cria um menu lateral que permite a navegação entre as diferentes páginas da aplicação: "Home", "Modelos Detalhados" e "Mapa de Ocorrências".
- **Coleta de Dados Iniciais:** Faz a primeira chamada à API do backend para obter os dados de previsão assim que o usuário acessa a aplicação.

### 1.2. `pages/home/home.py`

Esta é a página principal do sistema, onde as informações mais importantes são exibidas.

- **Seleção de Data:** Permite que o usuário escolha uma data para visualizar a previsão.
- **Previsão Geral:** Apresenta a probabilidade de alagamento para o dia selecionado e para o dia seguinte.
- **Mapa Interativo:** Um mapa de Santo André é exibido, com as bacias hidrográficas e áreas alagáveis destacadas. As cores das áreas mudam de acordo com a probabilidade de alagamento, fornecendo uma representação visual clara do risco.
- **Medidores de Probabilidade:** Para cada bacia hidrográfica, um medidor exibe a probabilidade de alagamento.
- **Previsão do Tempo:** Um gráfico mostra a previsão de temperatura e precipitação para as próximas horas.

### 1.3. `pages/home/utils.py`

Este arquivo contém funções auxiliares para a página `home`, como:

- **Funções de Cor:** Determinam as cores a serem usadas no mapa e nos medidores, com base nos valores de probabilidade.
- **Funções de Plotagem:** Funções para criar os gráficos de medidor e de previsão do tempo.
- **Dicionários:** Mapeiam os nomes das bacias e outros termos para uma exibição mais amigável.

### 1.4. `pages/models/models.py`

Esta página oferece uma visão mais detalhada dos modelos de previsão. Para cada
região (município e bacias), ela exibe a probabilidade individual de cada
modelo que compõe a previsão final. Isso permite uma análise mais aprofundada
dos resultados.

### 1.5. `pages/chamados/chamados.py`

Esta página incorpora um dashboard do Power BI que exibe um mapa de ocorrências
de alagamentos.

## 2. Tecnologias Utilizadas

- **Streamlit:** O principal framework usado para construir a interface do usuário.
- **Streamlit-Folium:** Para a exibição de mapas interativos.
- **Plotly:** Para a criação de gráficos (medidores e previsão do tempo).
- **Pandas:** Para a manipulação de dados.
- **Requests:** Para fazer chamadas à API do backend.
