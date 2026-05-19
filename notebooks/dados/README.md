## Fontes de dados PSA

### Organização do diretório `dados/`

| Subdiretório | Conteúdo |
|---|---|
| *(raiz)* | Dados primários consumidos pelo pipeline (parquet, csv, geojson, json). |
| `chuva_bacias/` | Séries horárias de precipitação por bacia hidrográfica (CEMADEN agregado). |
| `weather/` | Dados meteorológicos históricos e de forecast (OpenWeather, Open-Meteo/ERA5). |
| `results/` | Parquets de métricas e comparativos gerados por experimentos (`_run_modelos_*.py`). |

### Chamados

#### Chamados raw

**Arquivo:** `chamados_raw.csv`
**Registros:** ~65.000 | **Período:** 2003–2025

Chamados atendidos pela Defesa Civil de Santo André. Cada registro representa um evento com endereço, coordenadas, tipo de serviço solicitado/executado, datas de abertura e execução, e informações de interdição.

**Colunas principais:** `Data Abertura`, `Hora Abertura`, `Data Execução`, `Hora Execução`, `Serviço Solicitado`, `Serviço Executado`, `Endereço`, `Bairro`, `Longitude`, `Latitude`, `Encaminhamento`, `Observação`

Tipos de serviço incluem: deslizamentos, vistorias de edificação, incêndios, alagamentos, risco de árvore, materiais perigosos e ações comunitárias.

---

### Pluviometria

#### CEMADEN bruto

**Arquivo:** `cemaden_bruto.csv`
**Registros:** ~26 milhões | **Período:** 2016–2025 | **Delimitador:** `;`

Medições horárias de precipitação (mm) de 19 estações pluviométricas do CEMADEN distribuídas por Santo André.

**Colunas:** `municipio`, `codEstacao`, `uf`, `nomeEstacao`, `latitude`, `longitude`, `datahora`, `valorMedida`

> Atenção: `valorMedida`, `latitude` e `longitude` usam vírgula como separador decimal (locale brasileiro).

---

### Geoespacial

#### Bacias hidrográficas

**Arquivo:** `bacias.json`

Mapeamento de bairros de Santo André para suas bacias hidrográficas. Chave de junção espacial para agregações por bacia.

| Bacia | Bairros |
|---|---|
| `tamanduatei` | 67 bairros |
| `guarara` | 31 bairros |
| `meninos` | 15 bairros |
| `oratorio` | 14 bairros |

#### Piscinões ABC

**Arquivo:** `piscinoes_abc.json`
**Registros:** 27 reservatórios | **Municípios:** Santo André, São Bernardo do Campo, Diadema

Catálogo de piscinões e micro-reservatórios de controle de cheias da região do ABC Paulista. Inclui capacidade (m³), localização, gestão (municipal/estadual) e data de inauguração (1994–2024).

**Capacidade total:** ~2,67 milhões m³
