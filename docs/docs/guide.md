---
title: Guia operacional
sidebar_position: 2
slug: /guide
---

# Manual Operacional

Este manual descreve os procedimentos técnicos para configuração, execução e deploy do sistema de predição de alagamentos.

## 1. Configuração do Ambiente

A execução do sistema depende de variáveis de ambiente. O procedimento a seguir descreve como configurá-las.

### 1.1. Arquivos de Ambiente

O repositório inclui um arquivo `.env.example` como modelo. Para facilitar a gestão de diferentes ambientes (local, desenvolvimento, produção), um `Makefile` está disponível para gerar os arquivos necessários.

**1. Crie os arquivos de configuração:**
```bash
make envs
```

**2. Preencha as variáveis:**
Abra o arquivo correspondente ao ambiente desejado (ex: `.env.local`) e preencha as seguintes variáveis:

*   `API_URL`: URL de acesso ao backend quando o frontend roda fora do Docker (padrão: `http://localhost:8080`). No `docker compose`, o frontend usa `http://backend:8080`.
*   `MONGO_URI`: Connection string da instância MongoDB.
*   `OPENWEATHER_API_KEY`: Chave de acesso para a API do OpenWeather.

**3. Carregue as variáveis de ambiente:**
Antes de executar a aplicação, carregue as variáveis no terminal. Este comando deve ser executado sempre que uma nova sessão do terminal for iniciada.
```bash
# Exemplo para ambiente local
source .env.local
```
Por razões de segurança, os arquivos `.env.*` não são e não devem ser versionados no repositório.

## 2. Execução do Sistema (Recomendado)

A forma recomendada para executar o sistema completo é utilizando Docker Compose, que orquestra todos os serviços.

**1. Iniciar o sistema:**
O comando a seguir constrói as imagens e executa os contêineres em modo `daemon` (segundo plano).
```bash
docker compose up --build -d
```

**2. Verificar os serviços:**
*   **Frontend:** Acesse `http://localhost:8501` em um navegador.
*   **Backend:** Verifique o status dos endpoints.
    ```bash
    curl http://localhost:8080/region/santoandre
    curl http://localhost:8080/forecast-data/santoandre/openweather
    ```
    Uma resposta em formato JSON é esperada para cada requisição.

**3. Parar o sistema:**
Para encerrar todos os contêineres, utilize:
```bash
docker compose down
```

## 3. Execução de Módulos Individuais

Para cenários de depuração ou desenvolvimento focado, os módulos podem ser executados individualmente.

### 3.1. Backend (Sentry)
O serviço de backend pode ser executado isoladamente.
```bash
# Navegue até a pasta 'backend'
cd backend

# Construa a imagem
docker build -t psa-backend --build-arg NODE_ENV=local .

# Execute o contêiner
docker run --rm -p 8080:8080 -d psa-backend
```
Neste modo, a porta de acesso é a `8080`.

### 3.2. Frontend
O frontend pode ser executado via Docker ou diretamente com Streamlit.

**Via Docker:**
```bash
# Navegue até a pasta 'frontend'
cd frontend

# Construa a imagem e execute o contêiner
docker build -t psa-frontend .
docker run --rm -p 8501:8501 -d psa-frontend
```

**Via Streamlit (sem Docker):**
```bash
# Navegue até a pasta 'frontend'
cd frontend

# Instale as dependências
pip install -r requirements.txt

# Execute a aplicação
streamlit run app.py
```

### 3.3. Módulo Harvest
O `harvest` é o coletor de dados do OpenWeather. Sua execução isolada é útil para garantir a redundância da coleta. Requer Python `3.11`.

```bash
# Navegue até a pasta do módulo
cd backend/harvest

# Instale o pacote em modo editável
pip install -e .

# Execute o processo de coleta
psa-harvest --debug
```

### 3.4. Módulo Floodcast
O `floodcast` gera as predições com base nos dados coletados.
```bash
# Navegue até a pasta do módulo
cd backend/floodcast

# Instale o pacote
pip install -e .

# Execute o processo de inferência
psa-floodcast --debug
```

## 4. Deploy

O processo de deploy pode variar conforme o provedor de nuvem. Como exemplo, para um provedor baseado em Virtuozzo (como o SaveInCloud):

1.  Faça o upload das imagens `psa-backend` e `psa-frontend` para um registro de contêineres (ex: Docker Hub).
2.  No painel do provedor, utilize a opção de deploy a partir de uma imagem Docker.
3.  Configure as variáveis de ambiente na máquina virtual, conforme descrito na Seção 1.
