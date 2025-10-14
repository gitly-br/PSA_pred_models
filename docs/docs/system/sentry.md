---
title: Sentry
slug: /sentry
sidebar_position: 3
---

# API do Sentry

O Sentry atua como a API de backend para o Sistema de Predição de Alagamentos (PSA). Ele fornece os endpoints necessários para que o frontend e outros serviços consumam os dados de previsão e de ocorrências.

## 1. Rota de Previsão

Este endpoint retorna o resultado da previsão de alagamento para uma determinada região e data.

- **Método:** `GET`
- **Rota:** `/region/<region_name>`

**Parâmetros de URL:**

- `<region_name>` (string, obrigatório): O nome da região para a qual a previsão é solicitada. Atualmente, o valor `santoandre` é o único suportado.

**Argumentos Opcionais (Query String):**

- `date` (string, opcional): A data para a qual a previsão é solicitada, no formato `YYYY-MM-DD`. Se não for fornecida, a data atual é utilizada.

**Exemplo de Uso:**

```bash
curl http://localhost:8080/region/santoandre?date=2024-01-10
```

**Resposta de Sucesso (200 OK):**

```json
{
  "today": {
    "all": {
      "predict": 0,
      "proba": 0.3,
      "explanation": "Não há precipitação significativa prevista para o período",
      "rain_today": { ... },
      "models": { ... }
    },
    "tamanduatei": { ... },
    "oratorio": { ... },
    "meninos": { ... },
    "guarara": { ... }
  },
  "tomorrow": {
    "all": { ... }
  }
}
```

## 2. Rota de Dados de Entrada da Previsão

Este endpoint retorna os dados de previsão do tempo que foram utilizados como entrada para os modelos de Machine Learning.

- **Método:** `GET`
- **Rota:** `/forecast-data/<region>/<sourcename>`

**Parâmetros de URL:**

- `<region>` (string, obrigatório): A região para a qual os dados são solicitados (ex: `santoandre`).
- `<sourcename>` (string, obrigatório): A fonte dos dados de previsão do tempo (ex: `openweather`).

**Argumentos Opcionais (Query String):**

- `date` (string, opcional): A data para a qual os dados são solicitados, no formato `YYYY-MM-DD`. Se não for fornecida, a data atual é utilizada.

**Exemplo de Uso:**

```bash
curl http://localhost:8080/forecast-data/santoandre/openweather?date=2024-01-10
```

**Resposta de Sucesso (200 OK):**

```json
[
  {
    "dt": 1704855600,
    "temp": 22.5,
    "pressure": 1012,
    "humidity": 80,
    "wind_speed": 3.5,
    "rain": 0,
    "clouds": 75
  },
  ...
]
```

## 3. Rota de Ocorrências (Power BI)

Este endpoint fornece um arquivo CSV com os dados de ocorrências de alagamentos, para ser consumido pelo Power BI.

- **Método:** `GET`
- **Rota:** `/chamados_pbi/get_csv`

**Autenticação:**

Este endpoint requer autenticação básica (Basic Authentication).

- **Usuário:** `chamados_psa`
- **Senha:** `n0d817g2b307vd&@asdfGJV`

**Exemplo de Uso:**

```bash
curl -u chamados_psa:n0d817g2b307vd\&@asdfGJV http://localhost:8080/chamados_pbi/get_csv
```

**Resposta de Sucesso (200 OK):**

A resposta será um arquivo CSV para download com os dados das ocorrências.
