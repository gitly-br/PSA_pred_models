# Decisões Técnicas Registradas

## Decisões da sessão 2026-04-28 (modelagem V3→V5b)

### Avaliação honesta — não negociável daqui pra frente
- **Threshold escolhido por TimeSeriesSplit (5 splits walk-forward) no treino**, aplicado fixo no test.
- **Otimização por F1** (não F2) na curva PR do CV. F2 viesa demais para recall quando o target tem positivos suficientes (e foi o que fez V5 virar alarmista).
- **Bootstrap IC95** estratificado, 1000 reamostragens, sempre reportado junto da métrica pontual.
- **Métrica operacional adicional**: alarmes/mês e eventos capturados (X/Y) — número que a defesa civil entende.
- Custo aceito: 168 fits por rodada (×6 vs versão antiga).

### Champion model — GradBoost regularizado
Em todas as 4 bacias e em todas as iterações (V3→V5b), `GradientBoostingClassifier` com `max_depth=2, min_samples_leaf=10, subsample=0.8, max_features="sqrt", n_estimators=200, learning_rate=0.05` venceu RandomForest, ExtraTrees, LightGBM, XGBoost, AdaBoost e LogisticReg. Os modelos não-regularizados memorizam treino completamente (PR-AUC train ≈ 1.0).

### Champions por bacia (target enriquecido com fontes externas)
- **guarara** → V5b (peso 0.5 para fonte externa, threshold F1)
- **meninos** → V5-F1 (peso uniforme, threshold F1)
- **oratorio** → V5-F1
- **tamanduatei** → V4 (sem fonte externa) — a inclusão da fonte externa **piora** essa bacia, que já tem volume suficiente de chamados.

### Fonte externa de positivos
- `alagamentos_bacias.csv` (79 datas com flags por bacia) traz +79 positivos novos (sem chamado correspondente). Maior impacto em meninos (+81%).
- **Para bacias com poucos chamados (meninos): adicionar.** Para bacias com volume suficiente (tamanduatei): **não adicionar** (ou pesar muito menos).

### Estações da bacia meninos
- Cobertura real das 8 estações originais é **81,2%** (não 50,8% como nota antiga sugeria).
- Adicionada `354870814A` (Vila Vitória, SBC) — fora dos 3 km do centróide, mas captura +20 chamados (cobertura 92,3%).
- Aceito risco de chuva remota em troca do ganho de positivos.

## Validação de labels em duas fases

- **Fase 1: `confirmado_chuva`** — validação permissiva com qualquer estação da cidade. Elimina chamados sem nenhuma chuva registrada.
- **Fase 2: `confirmado_chuva_bacia`** — revalidação refinada usando apenas estações mapeadas para a bacia do chamado. Chamados confirmados na Fase 1 mas cuja bacia estava seca são rebaixados.
- **Motivo:** usar qualquer estação pode gerar falsos positivos de confirmação (chuva em bacia distante não valida enchente local).
- Artefato final `dados/chamados_enchente.parquet` deve conter ambas as colunas.

## Lições dos notebooks antigos (Modelos_SA.ipynb, Modelos_V1.ipynb)

Decisões validadas empiricamente que devem ser preservadas:

1. **Split temporal obrigatório** — train 2016-2022, test 2023-2024 (nunca random split) ⚠️ *Revisado em 2026-04-28: optou-se por random split estratificado no baseline porque o split temporal deixa oratorio sem positivos no teste (todos os 24 eventos são anteriores a 2024). Retornar ao split temporal em versões posteriores com mais dados.*
2. **Filtro sazonal** — remover meses 5-10 (seca), confirmado em ambos notebooks
3. **Undersampling por cluster** — KMeans nos negativos, sample de cada cluster
4. **Avaliação condicionada a percentil** — precision melhora dramaticamente em dias com chuva >p75; cenário operacional
5. **Modelagem por bacia** — cada bacia tem dinâmica diferente
6. **Recall > Precision** — perder enchente é pior que falso alarme (mas target Precision >50%)
7. **Forecast obrigatório em produção** — dados históricos não existem em tempo real

## Melhores features identificadas

**Histórico (CEMADEN + Open Weather):**
visibilidade média 12-18h, ponto de orvalho 6-12h, delta visibilidade, sensação térmica, delta precipitação

**Forecast:**
delta umidade 0-6h, delta ângulo do vento, umidade média 6-12h, probabilidade de precipitação, delta convecção

## Data Schema detalhado

- `chamados_raw.csv` — 65k chamados (2003-2025). Colunas: `data_abertura`, `hora_abertura`, `servico_solicitado`, `bairro`, `longitude`, `latitude`, `observacao`
- `cemaden_bruto.csv` — 26M registros horários de pluviometria (2016-2025). Separator `;`, vírgula decimal
- `bacias.json` — mapeamento bairro → bacia (meninos, oratorio, tamanduatei, guarara)
- `piscinoes_abc.json` — 27 piscinões com capacidade, ano inauguração
- `alagamentos_confirmados.csv` — 79 datas de eventos confirmados (precisa verificação)
- `alagamentos_bacias.csv` — mesmas 79 datas com flags por bacia (precisa verificação)
- `fonte_gpt.csv` — 52 eventos com evidência/fonte/link (gerado por GPT, precisa verificação)
- `maior_tres_verificado_gpt.csv` — 48 eventos adicionais verificados
