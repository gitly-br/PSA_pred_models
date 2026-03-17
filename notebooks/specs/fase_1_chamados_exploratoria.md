# Fase 1: Exploratória de Chamados + Validação de Labels

## Objetivo

Validar e rotular chamados de enchente (809.x) contra dados CEMADEN. Responde: **"Quais chamados correspondem a eventos reais validados por chuva, tanto cidade-wide quanto por bacia?"**

## Inputs

| Arquivo | Descrição |
|---------|-----------|
| `dados/chamados_raw.csv` | 65k chamados (2003-2025) |
| `dados/cemaden_bruto.csv` | 26M registros horários de pluviometria (2016-2025), sep `;`, vírgula decimal |
| `dados/bacias.json` | Mapeamento bairro → bacia (meninos, oratorio, tamanduatei, guarara) |
| `dados/alagamentos_confirmados.csv` | 79 datas de eventos confirmados |
| `dados/alagamentos_bacias.csv` | 79 datas com flags por bacia |
| `dados/fonte_gpt.csv` | 52 eventos com evidência/fonte/link (gerado por GPT) |
| `dados/maior_tres_verificado_gpt.csv` | 48 eventos adicionais verificados |

## Outputs

| Artefato | Descrição |
|----------|-----------|
| `dados/chamados_enchente.parquet` | Chamados 809.x com `confirmado_chuva` (bool, qualquer estação) e `confirmado_chuva_bacia` (bool, estações da bacia) |
| `dados/estacoes_bacia.json` | Mapeamento código estação CEMADEN → bacia |
| `dados/datas_enchente_consolidadas.csv` | Datas confirmadas deduplicadas de todas as fontes |

## Seções do notebook

### Já implementado

- **Imports e helpers** — remover_acentos, normalizar_bairro, converter_datahora, constantes
- **Carga e filtro de chamados** — leitura CSV, filtro 2016+, stats gerais
- **Normalização geográfica** — normalização de bairros, join com bacias, callout de cobertura
- **Filtro 809.x** — isolamento dos chamados de alagamento, callout
- **Carga CEMADEN** — botão de carga (26M linhas), parsing de datas e valores decimais
- **Agregação horária** — máximo horário entre todas as estações
- **Validação multi-janela** — janelas 6h/12h/24h/48h/72h com sliders `mo.ui.number`, tabela de confirmação por limiar

### A implementar

- **Consolidar datas externas** — carregar os 4 arquivos de validação, deduplicar por data, cruzar com chamados 809.x. Exibir cobertura cruzada.
- **Mapa de estações** — Plotly scattermapbox com as 19 estações CEMADEN + centróides dos bairros por bacia. Sanity check visual.
- **Mapeamento estação → bacia** — atribuir cada estação a uma ou mais bacias usando coordenadas. Exportar `estacoes_bacia.json`.
- **Validação por bacia (`confirmado_chuva_bacia`)** — revalidar cada chamado confirmado usando APENAS estações da bacia. Rebaixar se bacia estava seca.
- **Summary stats** — `mo.stat` cards e gráfico de barras plotly de taxas de confirmação por bacia.
- **Export** — salvar `chamados_enchente.parquet` e `datas_enchente_consolidadas.csv`.

## Decisões tomadas

_(nenhuma ainda)_

## Decisões pendentes

- Método de mapeamento estação-bacia: centróide mais próximo vs. manual?
- Limiares de chuva: hardcodar após exploração ou manter interativos?
- Pré-filtrar CEMADEN para estações de Santo André (códigos `354780901A`–`354780919A` + série G)?

## Dependências

Nenhuma — esta é a primeira fase do pipeline.
