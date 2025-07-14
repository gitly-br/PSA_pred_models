---
sidebar_position: 3
slug: /guide
---

# Guia de utilização do sistema

## 1. Rodando localmente

### 1.1. Variáveis de ambiente

O sistema depende das seguintes variáveis de ambiente para rodar:

* `API_URL` - Essa é a URL utilizada pelo frontend para acessar o backend.
* `MONGO_URI` - Essa é a *connection string* da instância do MongoDB que deve
  ser utilizada.
* `OPENWEATHER_API_KEY` - Chave de acesso ao serviço da *Openweather*

Para setar essa variáveis, o repositório conta com um arquivo `.env.example` 
que oferece o esqueleto para a criação de um scrip bash que preenche todas
essas variáveis de ambiente. Além disso, há um `Makefile` simples que cria 
os arquivos `.env.local`, `.env.dev` e `.env.prod` a partir do exemplo. A
ideia é facilitar a seleção de ambientes distintos para desenvolvimento local, 
remoto e produção. Para criar esses arquivos, rode:

```bash
make envs
```

Preencha os arquivos com suas variáveis manualmente. Para criar o ambiente, 
rode:

```bash
source .env.{local/dev/prod}
```

Por exemplo, para configurar um ambiente de desenvolvimento local:

```bash
source .env.local
```

As variáveis de ambiente não estão e nem estarão no repositório por questão
de segurança.

### 1.2. Utilizando o *docker compose* (RECOMENDADO)

A forma mais fácil de rodar todo o sistema é utilizando o `docker-compose.yaml`
disponibilizado na raíz do repositório. Ele já configura o sistema inteiro para
ser utilizado e testado. **Lembre-se que é necessário setar as variáveis de
ambiente antes de rodar o compose**. O comando é:

```bash
docker compose up -d -build
```

Isso vai criar as imagens necessárias e rodar os containeres do sistema em 
modo `daemon`. Para verificar o backend, basta rodar os seguintes requests:

```bash
curl http://localhost:8080/region/santoandre
```

```bash
curl http://localhost:8080/forecast_data/santoandre/openweather
```

Se tudo tiver dado certo, você vai ver uma resposta json para cada um desses 
requests. Lembre-se de que o sistema trabalha com dados em *cache*, de modo que 
só vai ter uma resposta com dados de inferência ou de previsão do tempo se o 
mongo para o qual estiver apontando o sistema estiver preenchido com valores
reais.

Para testar o frontend, basta abrir o navegador e acessar http://localhost:8501

### 1.3. Rodando apenas o backend

Caso queira rodar apenas o backend, você vai precisar navegar até o diretório
`backend` e rodar:

```bash
docker build -t psa-backend --build-arg NODE_ENV={local/dev/prod} .
```

Isso vai construir a imagem `psa-backend`, que você pode rodar usando:

```
docker run --rm psa-backend -d
```

Pronto, seu backend já está disponível. Há apenas uma modificação nos testes de
rota nesse caso. Veja os comandos a seguir:

```bash
curl http://localhost:8000/region/santoandre
curl http://localhost:8000/forecast_data/santoandre/openweather
```

Note que apenas a porta muda. Isso acontece pois no compose mapeamos a porta
8000 do backend para a 8080 do sistema raíz por uma questão de compatibilidade
entre as imagens.

Existe a opção de rodar o sistema sem container algum, mas não é recomendado.

### 1.4. Rodando apenas o frontend

De maneira similar, pode-se rodar o frontend do projeto entrando no diretório
`frontend` e rodando: 

```bash
docker build -t psa-frontend .
docker run --rm psa-frontend -d
```

Para testar, acesse http://localhost:8501

#### 1.4.1. Rodando o frontend sem container

Como o frontend é uma aplicação streamlit simples, é possível instalar todas
as dependências do projeto com:

```bash
pip install -r requirements.txt
```

E rodá-lo com:

```bash
streamlit run app.py
```

Essa forma não é recomendada, mas é viável e consideravelmente mais simples que
o setup do backend sem container.

### 1.5. Rodando somente o *harvest*

Um dos benefícios da nova arquitetura é a modularização do código. Embora
a imagem do *backend* agrupe os três módulos em um só, é possível rodar cada um
deles separadamente. A vantagem de fazer isso com o *harvest* é muito clara: 
redundância. Esse é o módulo que coleta dados da *openweather* para futuramente 
usar nas inferências. Ter esse módulo rodando em mais de uma máquina diminui 
drasticamente o risco de falhas de coleta de dados.

Para rodar somente o *harvest*, primeiro garanta que sua versão de Python é a
`3.11`. Para verificar a sua versão, rode:

```bash
python --version
```

:::tip Dica

Pode ser bastante oneroso instalar em seu sistema exatamente a versão de Python
necessária. Sendo assim, sugiro o uso de uma ferramenta de gerenciamento de
versões de python como o [pyenv](https://github.com/pyenv/pyenv). Sugiro fortemente
o uso de `venv` também. Para criar uma venv: 

```bash
python -m venv minha-venv
```

E para habilitá-la:

```bash
source ./minha-venv/bin/activate
```

:::

Após garantir a sua versão de Python, navegue até o diretório `backend/harvest`
e rode:

```bash
pip install .
```

Após a instalação, basta usar o comando `psa-harvest` para iniciar o processo.
Caso queira ver os logs de debug, apenas use o flag `--debug`.

### 1.6. Rodando apenas o *floodcast*

*Floodcast* é o módulo que carrega os modelos e faz a inferência a partir dos
dados coletados pelo *Harvest*. Sendo assim, a vantagem de rodar esse módulo
localmente é muito similar ao *Harvest*: redundância. Esse módulo gera o
*cache* de inferência para que a *API* apenas precise acessar os valores de
inferência pré-salvos.

Para instalar o *floodcast*, navegue até `backend/floodcast` e rode: 

```bash
pip install .
```

Após a instalação, basta utilizar o comando `psa-floodcast` para rodar o
módulo. O flag `--debug` mostra mais detalhes da execução.

### 1.7. Rodando apenas o *sentry*

*Sentry* é a API que busca as inferência pré-salvas e serve-as para um cliente.

**Não há muitos motivos para querer rodar o sentry sozinho**, mas se quiser
fazê-lo mesmo assim, aqui está o guia:

* Navegue até `backend/sentry`
* Rode `pip install -r requirements.txt`
* Rode `sanic run run.py`

## 2. Fazendo o *deploy*

Aqui a seção ficaria bastante extensa se considerarmos todas as possibilidades
de fornecedor de infraestrutura em nuvem. Sendo assim, vou apenas delinear o
processo necessário para o *SaveInCloud*, um fornecedor que usa um sistema
baseado no *Virtuozzo*.

Para subir o sistema, basta enviar as imagens `psa-backend` e `psa-frontend`
para o *Dockerhub* e, escolher a opção de deploy de imagem. **Lembre-se de
configurar as máquinas virtuais com as variáveis de ambiente descritas acima**.


