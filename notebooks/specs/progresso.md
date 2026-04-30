# Progresso do Pipeline

## Fase ativa: comparativo de fontes de precipitação (sessão 2026-04-30)

**Status:** Experimentos de modelagem V3→V7 concluídos (sessão anterior). Esta sessão investigou fontes alternativas de precipitação para substituir CEMADEN em produção. Resultado principal: ERA5-multipoint é viável para guarara/meninos, inviável para oratorio/tamanduatei.

**Próximo passo (retomada):** ver seção "Próximos passos detalhados" abaixo e seção "Fase 6 — comparativo de fontes" adicionada no final deste arquivo.

## Decisões tomadas nesta sessão (2026-04-30)

### Comparativo de fontes de precipitação

**Problema identificado:** o script anterior `_run_comparativo_fontes.py` usava GradBoost binário simples com `FEATURES_COMPAT` (sem features espaciais), produzindo resultados muito piores que o champion V7. Não era comparação justa.

**Bug corrigido em `_run_comparativo_multipoint.py`:** usava `max_day_lag1` como proxy para `max_dia` no target de severidade — data leak que inflava recall artificialmente (chegava a 97–100%). Corrigido para usar `max_dia` real do dia atual via `build_diario()`.

**Fontes pesquisadas:**
- CEMADEN nowcasting: sem API pública documentada. Algoritmo TOOCAN existe internamente.
- Open-Meteo archive API: retorna ERA5-Land (~11 km, 0.1°) por padrão quando consultado em múltiplos pontos próximos. Cobre 2016–2025, zero nulls, gratuito.
- ICON-EU (7 km): indisponível historicamente para Brasil via Open-Meteo.
- GFS via historical-forecast-api: disponível mas cobre Brasil a ~28 km, nulls em 2016.

**ERA5-Land multipoint:** baixados 5 pontos de grade únicos cobrindo as 4 bacias (dados em `dados/openmeteo_multipoint/`). Cada ponto é uma célula ERA5-Land genuinamente distinta (snap para coordenadas diferentes). Correlação entre pontos: r=0.88–0.95. Std diário máximo intra-bacia: 13–30 mm (sinal real em eventos convectivos).

**Mapeamento bacia → pontos ERA5-Land:**
- guarara: 3 pontos
- oratorio: 3 pontos
- meninos: 4 pontos
- tamanduatei: 3 pontos

**Resultados do comparativo (modelo V7 ordinal, FEATURES_V4 completas):**

| Experimento | Bacia | TPs | FPs | Pos | Precisão | Recall | PR-AUC | Alarmes/mês |
|---|---|---|---|---|---|---|---|---|
| CEM→CEM | guarara | 31 | 22 | 38 | 58% | 82% | 0.838 | 3.79 |
| CEM→CEM | meninos | 8 | 10 | 10 | 44% | 80% | 0.732 | 1.29 |
| CEM→CEM | oratorio | 21 | 22 | 23 | 49% | 91% | 0.664 | 2.53 |
| CEM→CEM | tamanduatei | 28 | 26 | 37 | 52% | 76% | 0.780 | 3.86 |
| ERA5mp→ERA5mp | guarara | 30 | 35 | 36 | 46% | 83% | 0.643 | 4.64 |
| ERA5mp→ERA5mp | meninos | 9 | 14 | 13 | 39% | 69% | 0.604 | 1.64 |
| ERA5mp→ERA5mp | oratorio | 14 | 251 | 14 | 5% | 100% | 0.563 | 15.59 |
| ERA5mp→ERA5mp | tamanduatei | 27 | 199 | 29 | 12% | 93% | 0.513 | 16.14 |
| CEM→ERA5mp | guarara | 18 | 44 | 36 | 29% | 50% | 0.700 | 4.43 |
| CEM→ERA5mp | meninos | 10 | 7 | 13 | 59% | 77% | 0.779 | 1.21 |
| CEM→ERA5mp | oratorio | 12 | 16 | 14 | 43% | 86% | 0.673 | 1.65 |
| CEM→ERA5mp | tamanduatei | 13 | 33 | 29 | 28% | 45% | 0.571 | 3.29 |

**Interpretação:**
- guarara e meninos (bacias menores, mais homogêneas): ERA5mp→ERA5mp PR-AUC 0.60–0.64, recall decente. Potencialmente utilizável com calibração de threshold.
- oratorio e tamanduatei (bacias maiores, mais estações CEMADEN): ERA5mp explode em FPs (251, 199), 15–16 alarmes/mês. Inviável operacionalmente.
- CEM→ERA5mp: meninos e oratorio ficam razoáveis (PR-AUC 0.67–0.78); guarara e tamanduatei pioram muito.
- Teto estrutural: ERA5-Land a 11 km suaviza eventos convectivos locais nas bacias maiores. Problema de resolução, não de modelo.

**Artefatos produzidos nesta sessão:**

| Artefato | Descrição |
|---|---|
| `dados/openmeteo_multipoint/pt_*.parquet` | 5 séries horárias ERA5-Land 2016–2025 (87.672 linhas cada) |
| `dados/openmeteo_multipoint/index.json` | Mapa bacia → lista de pontos lat/lon |
| `dados/comparativo_multipoint.parquet` | Tabela de resultados dos 3 experimentos × 4 bacias |
| `_download_openmeteo_multipoint.py` | Script de download dos pontos ERA5-Land |
| `_run_comparativo_multipoint.py` | Comparativo CEM→CEM / ERA5mp→ERA5mp / CEM→ERA5mp com modelo V7 |
| `dados/openweather_history.parquet` | OpenWeather histórico 1979–2024 (ponto único) |
| `dados/openweater/open_meteo_history.parquet` | ERA5-Land ponto único 2016–2025 (baseline) |

**Pendências desta sessão:**
- Avaliar se calibração de threshold separada por fonte melhora ERA5mp para guarara/meninos.
- Investigar por que CEM→ERA5mp é tão ruim para guarara/tamanduatei mas razoável para meninos/oratorio.
- Decidir se ERA5mp serve como fallback para guarara/meninos quando CEMADEN offline.
- Consolidar resultados no relatório Typst `specs/relatorio_forecast_comparativo.typ`.

## Próximos passos detalhados (pendências das discussões)

Cada item tem: **racional** (por que importa), **como fazer** (resumido), e **status** (não iniciado).

### A. Champion-by-basin oficial (consolidação)
- **Racional:** já temos os champions definidos (V4 para tamanduatei, V5-F1 para oratorio/meninos, V5b para guarara), mas não há script único que aplique a configuração certa por bacia em produção. Hoje seriam 4 scripts diferentes para gerar 4 inferências.
- **Como fazer:** criar `_run_modelos_champion.py` que, por bacia, lê target+features apropriado (com ou sem fonte externa, peso ajustado), treina o GradBoost regularizado, e gera predições + thresholds num formato unificado (parquet com `data, bacia, prob, alarme, threshold_usado`).
- **Saída esperada:** `dados/predicoes_champion.parquet` + `modelos/champion_<bacia>.pkl`.
- **Status:** não iniciado.

### B. Tentar esticar tamanduatei (única bacia onde V4 ainda vence V5*)
Discutimos algumas hipóteses não testadas. Em ordem de barateza:
1. **Peso da fonte externa por bacia** em vez de global. Para tamanduatei, peso 0.0 (=V4 efetivo). Para guarara/meninos, peso 0.5–1.0. Permite manter um único pipeline.
2. **Filtrar fonte externa por severidade.** Hipótese: eventos midiáticos da fonte externa são "fáceis demais" e puxam o modelo. Se cruzarmos `alagamentos_bacias.csv` com chuva máxima do dia e mantivermos só os com `max_dia ≥ p50` dos chamados confirmados da bacia, removemos eventos de jornal sobre alagamento sem chuva forte (drenagem entupida etc.).
3. **Endurecer regularização do GradBoost para tamanduatei** (`min_samples_leaf=20`, `max_depth=2`, mais `subsample=0.7`) — não testamos hiperparâmetros por bacia.
- **Status:** não iniciado.

### C. Calibração de probabilidades (isotônica)
- **Racional:** hoje a probabilidade `predict_proba` do GradBoost não está calibrada — `0.6` não significa "60% chance". Defesa civil quer comunicar risco quantitativo, não só "alarme/sem alarme".
- **Como fazer:** `CalibratedClassifierCV(base_estimator, method="isotonic", cv=TimeSeriesSplit(5))` envolvendo o champion. Comparar Brier score e reliability diagram antes/depois.
- **Status:** não iniciado.

### D. Ensemble por bacia (V4 + V5-F1)
- **Racional:** discutimos como complemento ao champion-by-basin. Em vez de escolher um modelo, pode-se promediar probabilidades de dois modelos por bacia (o V4 sem fonte externa + V5-F1 com fonte externa). Combina conservadorismo de V4 com sensibilidade de V5.
- **Como fazer:** treinar os dois separadamente; média geométrica das probabilidades; threshold escolhido no CV do ensemble.
- **Status:** discutido como opção, não testado. Pode bater champion-único em F2.

### E. Modelo multi-bacia (com bacia one-hot)
- **Racional:** estava no plano original (Bloco D do plano), mas decidimos manter modelos por bacia para preservar granularidade da defesa civil. Vale revisitar: pode-se **treinar** um modelo único multi-bacia para regularização (mais dados → menos overfit) e ainda **predizer por bacia** passando a feature one-hot. Saída por bacia preservada, ganho de regularização aproveitado.
- **Como fazer:** `df_ml` consolidado das 4 bacias com colunas `bacia_guarara, bacia_meninos, bacia_oratorio, bacia_tamanduatei` (one-hot); split temporal global; predict por bacia separadamente para reportar.
- **Status:** discutido, descartado naquela rodada, mas não testado.

### F. Critério de suspeito — afinar
- **Racional:** o critério atual (p25 + chuva ≥ p75 + fim de semana) descartou só 3 dias entre todas as bacias. Pode estar muito conservador. Discutimos que afrouxar é arriscado, mas não testamos níveis intermediários.
- **Como fazer:** grid de critérios:
  - Limiar de similaridade: p10, p25, p50.
  - Filtro contextual: só fim de semana / fim de semana OU madrugada / qualquer.
  - Para cada combinação, medir F2 do champion. Encontrar Pareto front entre "n_suspeitos descartados" e "F2 no test".
- **Status:** não iniciado. Pode ser ganho moderado; também serve como diagnóstico (se nenhum critério ajuda, descartamos a hipótese).

### G. Instrumentação (Bloco F do plano original)
- **Racional:** já temos 5 runs feitos (V3, V4, V5, V5-F1, V5b) com resultados em texto livre. Não há tabela canônica que permita responder "que mudança trouxe ganho real". Próxima iteração precisa disso para evitar regressão.
- **Como fazer:** `dados/experimentos.parquet` com 1 linha por (run_id, bacia, modelo, features_set, hiperparams, métricas_pontuais, IC95, threshold, data_run). Todos os scripts `_run_modelos_*.py` passam a appendar.
- **Status:** não iniciado. Barato, mas é prep para iterar mais rápido — não é ganho de modelo.

### H. Forecast (Fase 6 / Bloco G)
- **Racional:** pré-requisito para produção. Em tempo real a defesa civil não tem chuva passada — tem previsão. Modelos atuais leem chuva acumulada das últimas 72 h.
- **Como fazer:** integrar dados de forecast (Open Weather histórico ou alternativa). Reconstruir features V4 substituindo "chuva acumulada" por "chuva prevista". Tunar e comparar com baseline atual.
- **Status:** não iniciado. Bloqueia produção real, mas faz sentido só **depois** que A/B/C/D consolidarem o teto sem forecast.

### I. Endurecer/relaxar V5b com peso por bacia
- **Racional:** `V5b` aplicou peso 0.5 globalmente. Para guarara o ganho foi marginal; para tamanduatei foi negativo. Plausível que peso ótimo seja por bacia.
- **Como fazer:** grid `peso_externo ∈ {0.0, 0.25, 0.5, 0.75, 1.0}` por bacia. Reportar F2 com IC95 para cada (bacia, peso). Escolher o melhor.
- **Status:** não iniciado. Subsume o item B.1.

### J. Investigar precisão baixa em todas as bacias (precisão < 0.25)
- **Racional:** não discutimos a fundo, mas todas as bacias tem precisão entre 0.17 e 0.24 mesmo nos champions. Operacionalmente significa que **3 de cada 4 alarmes são falsos**. Pode haver teto estrutural — chuva forte por si só não garante enchente; depende de drenagem, manutenção, lixo, capacidade de piscinões etc.
- **Como fazer:**
  - Análise dos falsos positivos (FP) do champion: existe padrão? São dias de chuva forte sem alagamento por causa estrutural?
  - Cruzar com `dados/piscinoes_abc.json` (capacidade de piscinões) e estado da drenagem se houver.
  - Se for teto estrutural, comunicar à defesa civil como "alarme = atenção sugerida", não "enchente garantida".
- **Status:** não iniciado.

### K. Avaliar incluir alagamentos confirmados externos COMO TEST set, não só train
- **Racional:** hoje o test usa apenas chamados confirmados pós-T_CUT. Eventos da fonte externa pós-T_CUT estão no test (boa coisa). Mas eventos pré-T_CUT entram no treino. Não diagnosticamos se isso cria viés temporal (eventos de mídia podem ter padrão temporal — ex: reportagem mais comum em anos recentes).
- **Como fazer:** distribuição temporal dos eventos da fonte externa por ano vs distribuição dos chamados. Se houver viés, pesar por ano ou descartar fonte externa de anos com sub-representação.
- **Status:** não iniciado.

## Ordem sugerida para próxima sessão

1. **G (instrumentação)** primeiro — barato, e tudo que vem depois fica mais fácil de comparar.
2. **A (champion-by-basin oficial)** — congela o estado atual antes de mexer.
3. **F (afinar suspeito)** + **I (peso da fonte externa por bacia)** em paralelo — testes baratos com potencial de ganho.
4. **C (calibração)** — barato, melhora comunicação operacional sem mexer em modelo.
5. **D (ensemble)** ou **E (multi-bacia interno)** — só se 3+4 não esticarem F2 o suficiente.
6. **J (precisão baixa estrutural)** — análise diagnóstica; pode redefinir o problema.
7. **H (forecast)** — somente quando teto sem forecast estiver claro.

**O que falta no pipeline (resumo):**
- A (champion oficial), B (tamanduatei), C (calibração), D (ensemble), E (multi-bacia), F (suspeito), G (instrumentação), H (forecast), I (peso por bacia), J (precisão estrutural), K (viés temporal externa)

## Champions por bacia (estado atual)

GradBoost (`max_depth=2`, `min_samples_leaf=10`, `subsample=0.8`, `max_features="sqrt"`, `n_estimators=200`, `learning_rate=0.05`) é o melhor modelo em todas as bacias.

| Bacia | Champion | F2 | IC95 F2 | Recall | Precisão | Alarmes/mês | Eventos capt. |
|---|---|---|---|---|---|---|---|
| guarara     | V5b   | 0.51 | [0.28, 0.70] | 0.75 | 0.22 | 1.93 | 6/8 |
| meninos     | V5-F1 | 0.46 | [0.00, 0.75] | 0.67 | 0.20 | 0.71 | 2/3 |
| oratorio    | V5-F1 | 0.48 | [0.33, 0.61] | 0.88 | 0.17 | 2.28 | 7/8 |
| tamanduatei | V4    | 0.58 | [0.45, 0.70] | 0.91 | 0.24 | 3.00 | 10/11 |

## Decisões tomadas nesta sessão (2026-04-28)

### Bloco A — Avaliação honesta (V3 refatorado)
- **Threshold otimizado por F1 (não F2) via TimeSeriesSplit no treino** (5 splits walk-forward), aplicado fixo no test. Antes: threshold otimizado na curva PR do test → leak.
- **Bootstrap IC95** estratificado (1000 reamostragens) para PR-AUC, F2, recall, precisão.
- **Métrica operacional adicional**: alarmes/mês e eventos capturados (X/Y).
- Custo: 28 fits → 168 fits (×6). Aceito.
- **Resultado:** F2 caiu em todas as bacias quando o leak foi removido (guarara 0.37→0.27, oratorio 0.61→0.35). Ganhos do V3 vs anteriores eram parcialmente ilusão.

### Bloco B — Revalidação programática de estações (meninos)
- Hipótese inicial (no `progresso.md` antigo): cobertura de meninos era 50,8%. **Falsa.** Cobertura real das 8 estações originais sobre os 181 chamados é **81,2%**.
- Diagnóstico programático em `_diagnostico_meninos.py`: para cada chamado, qual estação CEMADEN confirma chuva (qualquer janela [1,3,6,24,48,72]h ≥ LIMS) na janela 72h retroativa.
- Greedy forward com raio 8 km → adicionada estação `354870814A` (Vila Vitória, SBC, 7,8 km do centróide). Cobertura 81,2% → 92,3% (+20 chamados confirmados).
- Aceito risco de chuva remota em troca do ganho de positivos.
- `dados/estacoes_bacia.json` atualizado (9 estações).
- `dados/chuva_bacias/chuva_meninos.parquet` regenerado (10 colunas: hora + 9 estações).
- Artefato: `dados/_meninos_revalidacao.json` (decisão registrada).

### Bloco C — Features V4 (`_run_modelos_v4.py`)
27 features (vs 16 do V3). Adicionadas:
- **Espaciais entre estações:** `chuva_mean_mm`, `chuva_std_mm`, `n_chovendo` (estações com >1 mm) → derivam `mean_day_lag1`, `std_day_lag1`, `n_chovendo_max_lag1`.
- **Regime/intensidade:** `pico_1h_lag1`, `horas_intensas_lag1` (horas ≥ 5 mm).
- **Saturação:** API com `K∈{0.70, 0.85, 0.95}` (3 features); `acum_7d`, `acum_30d` (rolling sum shiftado).
- **Sazonalidade:** `mes_sin`, `mes_cos` (cíclico).
- Mantidas: 12 lags `acc_6h_lag_*`, 3 lags `max_day_lag*`.
- **Resultado:** F2 subiu em todas as bacias (guarara +0.16, meninos +0.28, oratorio +0.12, tamanduatei +0.10). Train PR-AUC subiu (0.89–0.98) — overfit estrutural não cedeu, mas o test ganhou.

### Bloco D — Target enriquecido + suspeitos (V5/V5b)
- **Diagnóstico (`_diagnostico_dias_suspeitos.py`):** para cada bacia, calcula similaridade euclidiana normalizada de cada negativo ao positivo mais próximo (features: `max_dia, acum_dia, mean_dia, n_chovendo_max, horas_intensas, api_085`).
- **Fonte externa** (`alagamentos_bacias.csv`): +25 positivos novos em guarara, +17 em meninos, +6 em oratorio, +31 em tamanduatei. **+79 total.**
- **Critério de suspeito (restrito):** dist ≤ p25 intra-positivos **E** chuva ≥ p75 dos positivos **E** fim de semana. Resulta em apenas 2 (guarara) + 1 (meninos) suspeitos excluídos.
- **V5 (peso uniforme):** target = chamado ∪ externo. Recall subiu para ~1.00 mas precisão despencou (0.09–0.13). Alarmes/mês explodiu (tamanduatei: 6,4).
- **V5-F1 (threshold por F1 em vez de F2):** alarmes caíram (~2/mês), F2 médio subiu para 0.47, recall caiu para 0.64–0.88. Trade-off operacional muito melhor.
- **V5b (peso 0,5 para fonte externa, F1):** train PR-AUC caiu (overfit menor), mas ganhos no test foram marginais (~0.01–0.02 F2). Tamanduatei continua melhor no V4.

## Decisões pendentes
- Selecionar champion-por-bacia oficialmente (script de inferência única).
- Avaliar peso da fonte externa por bacia (peso por bacia pode ser melhor que peso global).
- Avaliar se vale endurecer ou afrouxar critério de suspeito (hoje muito restrito).

## Artefatos

| Artefato | Existe? | Origem |
|----------|---------|--------|
| `dados/chamados_por_bacia.parquet` | Sim | Fase 1 |
| `dados/estacoes_bacia.json` | Sim (9 est. meninos pós-Bloco B) | Fase 2 |
| `dados/chuva_bacias/chuva_{bacia}.parquet` | Sim (meninos regenerado) | preprocessamento_chuva.py |
| `dados/cemaden_abcd.parquet` | Sim | minio_import |
| `dados/alagamentos_bacias.csv` | Sim (79 datas, flags por bacia) | Fase 1 |
| `dados/_meninos_revalidacao.json` | Sim | `_diagnostico_meninos.py` |
| `dados/_dias_suspeitos.parquet` | Sim | `_diagnostico_dias_suspeitos.py` |
| `dados/_novos_positivos_externos.parquet` | Sim | `_diagnostico_dias_suspeitos.py` |

## Scripts de experimento

| Script | Propósito | Saída |
|--------|-----------|-------|
| `_run_modelos_v3.py` | Baseline V3 (16 features, avaliação honesta) | stdout |
| `_run_modelos_v4.py` | V4 (27 features, mesmo target) | stdout |
| `_run_modelos_v5.py` | V5 (target enriquecido + suspeitos, threshold F1) | stdout |
| `_run_modelos_v5b.py` | V5b (peso 0,5 fonte externa) | stdout |
| `_diagnostico_meninos.py` | Bloco B — revalidação estações meninos | `_meninos_revalidacao.json` |
| `_diagnostico_dias_suspeitos.py` | Bloco D — diagnóstico dias suspeitos | `_dias_suspeitos.parquet` |

## Pipeline (notebooks)

| Fase | Status |
|------|--------|
| chamados_exploratoria.py | ✅ Concluído |
| pluviometria_exploratoria.py | ✅ Concluído |
| preprocessamento_chuva.py | ✅ Concluído (regenerar quando estações mudarem) |
| modelagem_baseline.py | ✅ Concluído |
| modelagem_temporal.py | ✅ Concluído |
| modelagem (V3/V4/V5/V5b) | 🔄 Em iteração — scripts `_run_modelos_*.py` |
| forecast_integracao.py | Não iniciada |

## Notas de retomada (próxima sessão)

Ler primeiro:
1. **`specs/relatorio_modelagem.md`** — narrativa completa com todos os resultados, racionais e tabelas.
2. **Este arquivo (progresso.md)** — estado atual e próximo passo.
3. `specs/decisoes_tecnicas.md` — decisões duráveis acumuladas.

Para reproduzir resultados: `uv run python _run_modelos_v5b.py` (ou v3/v4/v5). Cada um demora ~25 min (168 fits cada).

---

## Histórico de sessões anteriores (preservado)

### Notas (2026-04-07)
- Substituído filtro de outliers CEMADEN por `min_chamados` (ui.number, padrão 3).
- Diadema removida do parquet CEMADEN; Mauá adicionada — 5,1M linhas, 4 municípios.
- Filtro `municipio == "SANTO ANDRÉ"` removido da carga do CEMADEN.
- Export `chamados_por_bacia.parquet` agora usa apenas chamados confirmados por chuva.

### Notas (2026-03-16)
- Refatoração completa de performance: Polars nativo, Altair 6.0, células de constantes e `lims` separadas.
- Filtro de outliers CEMADEN com stats de remoção.
- Gráfico de perfil interativo: seleção por clique, janela 72h, banda/risco.
- Lógica de `dt_ajustado`: pico de 1h dentro da melhor janela acumulada (1h/3h/6h) nas 72h anteriores.
- Janelas de evento (`event_start`/`event_end`).
- Tabela de dias suspeitos e seção "Alagamentos confirmados sem chamados".
