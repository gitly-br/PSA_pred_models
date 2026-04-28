# Decisões Técnicas Registradas

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
