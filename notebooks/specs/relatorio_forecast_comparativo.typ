#set document(title: "Análise Comparativa: Forecast vs Histórico — Dados Meteorológicos", author: "PSA / Santo André")
#set page(margin: (x: 2.5cm, y: 2.5cm))
#set text(font: "Liberation Serif", size: 11pt, lang: "pt")
#set heading(numbering: "1.")
#show heading: it => { v(0.6em); it; v(0.3em) }
#show table: it => { set text(size: 9pt); it }

#align(center)[
  #text(size: 16pt, weight: "bold")[Análise Comparativa: Forecast vs Histórico]
  #linebreak()
  #text(size: 12pt)[Dados Meteorológicos — Santo André, SP]
  #linebreak()
  #text(size: 10pt, fill: gray)[Fase 6 — Integração de Forecast | PSA Enchentes]
]

#v(1em)
#line(length: 100%)
#v(0.5em)

= Contexto

Este relatório investiga se dados históricos de reanalysis (ERA5 via Open-Meteo) podem ser usados
como proxy de forecast para o treinamento do modelo de enchentes da Fase 6, dada a
indisponibilidade de arquivos históricos de previsão para o período completo (2016–2025).

A análise usa dados do *TomorrowIO* coletados em produção entre *novembro/2023 e março/2024*
(109 dias úteis), que registraram a previsão horária junto com o horário exato de consulta (`Now`).
Isso permite calcular o *lead time real* de cada forecast e avaliar como a qualidade da previsão
varia com a antecedência.

*Referências:*
- *ERA5*: reanalysis horário Open-Meteo para Santo André (lat -23.65, lon -46.53)
- *CEMADEN*: pluviômetros da bacia Tamanduateí (média entre estações), ground truth local
- *TomorrowIO*: forecasts horários, lead 0–120h, com `rainIntensity` (mm/h)

= Fontes de dados disponíveis

#table(
  columns: (auto, auto, auto, auto, auto, auto),
  stroke: 0.5pt,
  fill: (col, row) => if row == 0 { luma(230) } else { none },
  [*Fonte*], [*Tipo*], [*Período*], [*Lead time*], [*Chuva*], [*Gratuito*],
  [Open-Meteo ERA5], [Histórico reanalysis], [1940–2025], [—], [precipitation_mm], [Sim],
  [TomorrowIO], [Forecast arquivado], [nov/2023–mar/2024], [D-5 a D0], [rainIntensity mm/h], [Sim],
  [VisualCrossing], [Forecast arquivado], [nov/2023–mar/2024], [D-14 a D0], [precip mm/h], [Sim],
  [ClimaTempo], [Forecast arquivado], [nov/2023–mar/2024], [D-2 a D+1], [rain_precipitation mm], [Sim],
  [OpenWeather forecast], [Forecast arquivado], [nov/2023–mar/2024], [D-5 a D0], [3h mm], [Sim],
  [NOAA GFS (AWS S3)], [Forecast arquivado], [2015–2025], [até D+16], [APCP mm/3h], [Sim*],
)
#text(size: 8pt, fill: gray)[\* NOAA GFS disponível via AWS, mas arquivos GRIB2 volumosos (~500 MB cada run)]

= Qualidade do ERA5 vs CEMADEN (período completo 2016–2025)

Avaliação do ERA5 como substituto para precipitação observada local:

#table(
  columns: (auto, auto, auto, auto, auto),
  stroke: 0.5pt,
  fill: (col, row) => if row == 0 { luma(230) } else { none },
  [*Métrica*], [*Valor*], [], [*Métrica*], [*Valor*],
  [Correlação Pearson diária (r)], [0.578], [], [Bias médio (ERA5 − CEMADEN)], [+2.06 mm/dia],
  [Concordância dias chuvosos (>2 mm)], [81%], [], [ERA5 média diária], [3.62 mm],
  [Dias com dados], [3.653], [], [CEMADEN média diária], [1.55 mm],
)

*Observação:* ERA5 superestima sistematicamente (+2 mm/dia) e subestima eventos extremos
(nos 10 maiores eventos do CEMADEN, ERA5 registrou em média 2–3× menos). Isso é esperado
para reanalysis de grade 10 km frente a eventos convectivos urbanos pontuais.

= Análise 1 — Estabilidade do forecast conforme o lead time diminui

Para cada hora-alvo no período, foram coletadas múltiplas previsões do TomorrowIO em
momentos diferentes (até 24 consultas por dia via `Now`). A tabela abaixo mostra o
quanto o forecast para uma mesma hora muda conforme a previsão foi feita mais cedo ou
mais tarde.

#table(
  columns: (auto, auto, auto, auto),
  stroke: 0.5pt,
  fill: (col, row) => if row == 0 { luma(230) } else { none },
  [*Transição de lead*], [*Correlação (r)*], [*MAE (mm/h)*], [*Interpretação*],
  [72–120h → 48–72h], [0.222], [0.313], [Muito instável — previsões de 3–5 dias quase aleatórias entre si],
  [48–72h → 24–48h],  [0.412], [0.298], [Moderado — alguma consistência em escala de 2 dias],
  [24–48h → 12–24h],  [0.231], [0.390], [Queda abrupta — D+1 não converge de D+2],
  [12–24h → 6–12h],   [0.237], [0.348], [Fraco — mesmo com 6–12h de antecedência, alto ruído],
  [6–12h → 3–6h],     [0.660], [0.247], [Bom — previsões de 3–6h são consistentes entre si],
  [3–6h → 0–3h],      [0.044], [0.641], [*Queda paradoxal* — ver nota abaixo],
)

*Nota sobre 3–6h → 0–3h:* a correlação cai para r=0.044 no intervalo mais próximo. Hipótese:
o TomorrowIO usa uma transição de modelo (NWP → nowcasting) nas últimas horas que introduce
descontinuidade. Ou há poucas observações nesse bin (efeito de borda de coleta).

*Conclusão da Análise 1:* forecasts com lead \> 24h têm correlação intra-bin fraca (r < 0.25),
indicando que a previsão muda substancialmente até 24h antes do evento. O único intervalo
estável é 3–12h de antecedência.

= Análise 2 — Forecast diário vs ERA5 e CEMADEN por janela de lead

Precipitação diária estimada: média dos runs disponíveis por hora-alvo, depois soma das 24h.

#table(
  columns: (auto, auto, auto, auto, auto, auto, auto, auto, auto),
  stroke: 0.5pt,
  fill: (col, row) => if row == 0 { luma(230) } else { none },
  [*Lead*], [*N dias*], [*Fcst média\ (mm/dia)*], [*r vs ERA5*], [*r vs CEM*],
  [*Bias\ ERA5*], [*Bias\ CEM*], [*RMSE\ ERA5*], [*Conc >2mm\ vs CEM*],
  [0–3h],   [85], [2.87], [0.581], [0.543], [−2.18], [+0.48], [6.57], [81%],
  [3–6h],   [85], [5.76], [0.221], [0.271], [+0.71], [+3.38], [17.29],[71%],
  [6–12h],  [85], [3.78], [0.299], [0.363], [−1.48], [+1.50], [12.82],[77%],
  [12–24h], [85], [5.56], [0.465], [0.403], [+0.10], [+2.98], [13.23],[77%],
  [24–48h], [98], [5.00], [0.588], [0.502], [−0.14], [+2.45], [7.15], [70%],
  [48–72h], [98], [4.81], [0.642], [0.629], [−0.33], [+2.26], [6.35], [68%],
  [72–120h],[99], [4.56], [0.471], [0.341], [−0.62], [+1.87], [6.96], [63%],
)

#text(size: 8pt, fill: gray)[ERA5 média: 5.05 mm/dia | CEMADEN média: 2.38 mm/dia]

*Destaques:*

- *48–72h tem a maior correlação com ERA5 (r=0.642)* — contraintuitivo, mas pode refletir que
  o ERA5 captura climatologia de fundo melhor do que eventos de curto prazo.
- *0–3h tem melhor correlação com CEMADEN (81% concordância)* — o forecast de curto prazo
  é o melhor preditor do que realmente acontece localmente.
- *3–6h e 6–12h têm correlações baixas* (~0.22–0.36) — zona de transição de modelo, maior
  incerteza.
- *ERA5 vs CEMADEN segue o mesmo padrão do forecast vs CEMADEN*, com bias positivo
  similar (~+2 mm), sugerindo que o problema é estrutural (resolução espacial) e não
  específico do tipo de dado.

= Análise 3 — ERA5 como proxy de forecast para treinamento

A questão central: *usar ERA5 como feature de precipitação no treinamento introduz viés
relevante em relação ao que estaria disponível em produção (forecast D+1)?*

#table(
  columns: (auto, auto, auto),
  stroke: 0.5pt,
  fill: (col, row) => if row == 0 { luma(230) } else { none },
  [*Comparação*], [*r diário*], [*Interpretação*],
  [ERA5 vs CEMADEN (ground truth)], [0.578], [ERA5 captura ~1/3 da variância local],
  [Forecast 24–48h vs ERA5], [0.588], [Forecast D+1 ≈ ERA5 em termos de correlação],
  [Forecast 24–48h vs CEMADEN], [0.502], [Forecast D+1 não é melhor que ERA5 vs CEMADEN],
  [Forecast 0–3h vs CEMADEN], [0.543], [Melhor forecast disponível ≈ ERA5 vs CEMADEN],
)

*Conclusão:* a correlação do forecast D+1 (24–48h) com ERA5 é r=0.588, praticamente
idêntica à correlação do ERA5 com CEMADEN (r=0.578). Isso indica que, do ponto de vista
do modelo de ML, *treinar com ERA5 ou com forecast D+1 produziria features de qualidade
equivalente*. O viés de treino/inferência introduzido por usar ERA5 é da mesma ordem de
grandeza do ruído natural entre forecast e observação.

= Análise 4 — Performance do modelo com cada fonte de precipitação

Experimento: GradBoost V4 treinado sempre com CEMADEN; avaliado com features
reconstruídas de cada fonte. Features normalizadas via QuantileTransformer ajustado
no treino CEMADEN (mapeamento quantil → normal padrão por bacia).

*Nota metodológica:* `std_day_lag1` e `n_chovendo_max_lag1` são features espaciais
derivadas de múltiplas estações CEMADEN — ERA5 e TIO têm uma única série, portanto
`chuva_std_mm = 0` sempre. Após quantile transform isso gera valor extremo (−5 σ),
destruindo as predições. Solução: *features compatíveis* excluem essas duas colunas.
`CEMADEN_v4` = features completas (V4 original). `CEMADEN_base` = mesmas features
compatíveis que ERA5/TIO para comparação justa.

#table(
  columns: (auto, auto, auto, auto, auto, auto, auto, auto),
  stroke: 0.5pt,
  fill: (col, row) => if row == 0 { luma(230) } else if calc.rem(row, 4) == 1 { luma(245) }
                      else if calc.rem(row, 4) == 2 { luma(250) }
                      else if calc.rem(row, 4) == 3 { luma(245) } else { none },
  [*Bacia*], [*Fonte*], [*F2*], [*IC95 F2*], [*Recall*], [*Precisão*], [*Eventos*], [*Alarmes/mês*],
  [guarara],      [CEMADEN v4],   [0.341], [\[0.11, 0.61\]], [0.38], [0.25], [3/8],  [0.86],
  [guarara],      [CEMADEN base], [0.357], [\[0.10, 0.60\]], [0.50], [0.17], [4/8],  [1.71],
  [guarara],      [ERA5],         [0.089], [\[0.00, 0.28\]], [0.12], [0.04], [1/8],  [1.71],
  [guarara],      [TIO D+1],      [0.000], [\[0.00, 0.00\]], [0.00], [0.00], [0/3],  [2.00],
  [meninos],      [CEMADEN v4],   [0.588], [\[0.00, 0.94\]], [0.67], [0.40], [2/3],  [0.36],
  [meninos],      [CEMADEN base], [0.278], [\[0.00, 0.72\]], [0.33], [0.17], [1/3],  [0.43],
  [meninos],      [ERA5],         [0.000], [\[0.00, 0.00\]], [0.00], [0.00], [0/3],  [0.36],
  [oratorio],     [CEMADEN v4],   [0.465], [\[0.22, 0.71\]], [0.67], [0.21], [4/6],  [1.12],
  [oratorio],     [CEMADEN base], [0.448], [\[0.38, 0.54\]], [1.00], [0.14], [6/6],  [2.53],
  [oratorio],     [ERA5],         [0.066], [\[0.00, 0.21\]], [0.17], [0.02], [1/6],  [3.06],
  [tamanduatei],  [CEMADEN v4],   [0.562], [\[0.43, 0.68\]], [0.91], [0.22], [10/11],[3.21],
  [tamanduatei],  [CEMADEN base], [0.542], [\[0.38, 0.69\]], [0.82], [0.23], [9/11], [2.79],
  [tamanduatei],  [ERA5],         [0.172], [\[0.00, 0.42\]], [0.18], [0.14], [2/11], [1.00],
  [tamanduatei],  [TIO D+1],      [0.000], [\[0.00, 0.00\]], [0.00], [0.00], [0/4],  [0.00],
)

#text(size: 8pt, fill: gray)[
  TIO D+1 = janela nov/2023–mar/2024 (4 meses, poucos eventos). Meninos e Oratorio não têm eventos TIO.
]

*Conclusões:*

- *CEMADEN_base ≈ CEMADEN_v4* em tamanduateí (F2 0.542 vs 0.562): remover as features
  espaciais custa ~3% de F2 — perda pequena, confirmando que o sinal principal vem das
  features de acumulação temporal.

- *ERA5 cai para F2 0.09–0.17* mesmo com features compatíveis: o ERA5 subestima os
  picos de precipitação que disparam o modelo (API e max_day ficam em quantis baixos
  mesmo após normalização). Não é problema de escala — é informação estruturalmente
  ausente (resolução 10 km vs eventos convectivos locais).

- *TIO D+1 = F2 0.000* em todas as bacias: janela de teste tem 0–4 eventos positivos
  (muito pouco), e TIO rainIntensity (mm/h) tem distribuição muito diferente de CEMADEN —
  o quantile mapping não transfere bem com tão poucos dados de referência.

- *Implicação direta:* usar ERA5 como substituto de CEMADEN no modelo atual *não funciona*
  — haveria queda de F2 de ~0.55 para ~0.10. O CEMADEN é insubstituível como fonte primária
  de precipitação para o modelo. ERA5/forecast pode ser *feature adicional*, não substituta.

= Análise 5 — Curvas Precision-Recall por fonte

Comparação da curva PR completa (todos os thresholds) e do ponto de operação
(threshold calibrado por CV no treino CEMADEN). CEMADEN e ERA5: test set completo
(T\_CUT → dez/2025). TIO D+1: janela de overlap nov/2023–mar/2024.

*AUPRC* (área sob curva PR) e *precisão alcançável* por nível fixo de recall:

#table(
  columns: (auto, auto, auto, auto, auto, auto, auto, auto, auto),
  stroke: 0.5pt,
  fill: (col, row) => if row == 0 { luma(230) } else { none },
  [*Bacia*], [*Fonte*], [*N+*], [*AUPRC*], [*Recall\ @thr*], [*Prec\ @thr*], [*Prec\ @R≥0.5*], [*Prec\ @R≥0.7*], [*Prec\ @R≥0.9*],
  [guarara],     [CEMADEN],  [8],  [0.375], [0.50], [0.167], [0.333], [0.194], [0.121],
  [guarara],     [ERA5],     [8],  [0.027], [0.12], [0.042], [0.019], [0.019], [0.019],
  [guarara],     [TIO D+1],  [3],  [0.024], [0.00], [—],     [0.035], [0.035], [0.035],
  [meninos],     [CEMADEN],  [3],  [0.255], [0.33], [0.167], [0.250], [0.250], [0.250],
  [meninos],     [ERA5],     [3],  [0.007], [0.00], [—],     [0.010], [0.010], [0.010],
  [oratorio],    [CEMADEN],  [6],  [0.267], [1.00], [0.140], [0.286], [0.250], [0.146],
  [oratorio],    [ERA5],     [6],  [0.031], [0.17], [0.019], [0.042], [0.042], [0.012],
  [tamanduatei], [CEMADEN],  [11], [0.392], [0.82], [0.231], [0.400], [0.400], [0.238],
  [tamanduatei], [ERA5],     [11], [0.052], [0.18], [0.143], [0.040], [0.040], [0.035],
  [tamanduatei], [TIO D+1],  [4],  [0.037], [0.00], [—],     [0.045], [0.045], [0.045],
)

*Leitura das colunas:*
- *AUPRC*: área sob curva PR — 1.0 é perfeito; baseline aleatório ≈ prevalência (~2–5%)
- *Recall\@thr / Prec\@thr*: ponto de operação com threshold calibrado no treino
- *Prec\@R≥X*: melhor precisão alcançável mantendo recall ≥ X (qualquer threshold)

= Análise 6 — ERA5 treinado como ERA5 (comparação justa)

A análise anterior treinava com CEMADEN e testava com ERA5 — mismatch de distribuição.
Aqui treinamos *e* testamos com cada fonte, usando as mesmas features compatíveis.
Cinco experimentos por bacia:

- *CEM→CEM (V4)*: treino CEMADEN, features completas (V4 original, inclui espaciais)
- *CEM→CEM (base)*: treino CEMADEN, features compatíveis (sem std/n\_chovendo)
- *ERA5→ERA5*: treino ERA5, teste ERA5, features compatíveis — comparação justa
- *CEM→ERA5*: treino CEMADEN, teste ERA5 — simula troca de fonte em produção
- *CEM→TIO D+1*: treino CEMADEN, teste TIO na janela de overlap

#table(
  columns: (auto, auto, auto, auto, auto, auto, auto, auto, auto, auto),
  stroke: 0.5pt,
  fill: (col, row) => if row == 0 { luma(230) }
                      else if calc.rem(row, 5) == 1 { luma(240) }
                      else { none },
  [*Bacia*], [*Experimento*], [*N+*], [*AUPRC*], [*F2*], [*Recall*], [*Precisão*], [*P\@R≥0.5*], [*P\@R≥0.7*], [*P\@R≥0.9*],
  [guarara], [CEM→CEM (V4)],   [8],  [0.367], [0.341], [0.375], [0.250], [0.308], [0.182], [0.131],
  [guarara], [CEM→CEM (base)], [8],  [0.375], [0.357], [0.500], [0.167], [0.333], [0.194], [0.121],
  [guarara], [ERA5→ERA5],      [8],  [0.027], [0.109], [0.875], [0.024], [0.037], [0.037], [0.020],
  [guarara], [CEM→ERA5],       [8],  [0.027], [0.089], [0.125], [0.042], [0.019], [0.019], [0.019],
  [guarara], [CEM→TIO D+1],    [3],  [0.024], [0.000], [0.000], [—],     [0.035], [0.035], [0.035],
  [meninos], [CEM→CEM (V4)],   [3],  [0.328], [0.588], [0.667], [0.400], [0.400], [0.250], [0.250],
  [meninos], [CEM→CEM (base)], [3],  [0.255], [0.278], [0.333], [0.167], [0.250], [0.250], [0.250],
  [meninos], [ERA5→ERA5],      [3],  [0.012], [0.027], [0.333], [0.006], [0.010], [0.009], [0.009],
  [meninos], [CEM→ERA5],       [3],  [0.007], [0.000], [0.000], [—],     [0.010], [0.010], [0.010],
  [oratorio],[CEM→CEM (V4)],   [6],  [0.208], [0.465], [0.667], [0.211], [0.250], [0.250], [0.207],
  [oratorio],[CEM→CEM (base)], [6],  [0.267], [0.448], [1.000], [0.140], [0.286], [0.250], [0.146],
  [oratorio],[ERA5→ERA5],      [6],  [0.022], [0.123], [0.500], [0.031], [0.034], [0.019], [0.015],
  [oratorio],[CEM→ERA5],       [6],  [0.031], [0.066], [0.167], [0.019], [0.042], [0.042], [0.012],
  [taman.],  [CEM→CEM (V4)],   [11], [0.371], [0.562], [0.909], [0.222], [0.333], [0.333], [0.286],
  [taman.],  [CEM→CEM (base)], [11], [0.392], [0.542], [0.818], [0.231], [0.400], [0.400], [0.238],
  [taman.],  [ERA5→ERA5],      [11], [0.053], [0.108], [0.273], [0.032], [0.053], [0.044], [0.043],
  [taman.],  [CEM→ERA5],       [11], [0.052], [0.172], [0.182], [0.143], [0.040], [0.040], [0.035],
  [taman.],  [CEM→TIO D+1],    [4],  [0.037], [0.000], [0.000], [—],     [0.045], [0.045], [0.045],
)

*Conclusões consolidadas:*

+ *ERA5→ERA5 não resolve o problema.* Mesmo treinando e testando com ERA5, o AUPRC
  permanece em 0.012–0.053 — idêntico ao CEM→ERA5. O modelo treinado com ERA5 aprende
  que "dias com ERA5 alto = flood", mas como ERA5 não distingue bem os eventos extremos
  da região, o sinal simplesmente não existe na fonte. Não é mismatch de treino/teste
  — é ausência de informação.

+ *Exceção parcial em guarara (ERA5→ERA5):* recall=0.875 com precisão=0.024 — o modelo
  detecta quase todos os eventos, mas dispara alarmes em 97% dos dias. Inútil
  operacionalmente (1 alarme real para cada 40 falsos).

+ *CEM→ERA5 vs ERA5→ERA5:* resultados quase idênticos (AUPRC 0.027 vs 0.027 em guarara;
  0.052 vs 0.053 em tamanduateí). Isso confirma que o problema é *na fonte ERA5*, não no
  mismatch de treino — mesmo um modelo otimizado para ERA5 não consegue performance útil.

+ *TIO D+1:* inconclusivo por falta de dados (3–4 eventos). AUPRC 0.024–0.037 é
  compatível com performance aleatória.

+ *Razão fundamental:* enchentes em Santo André são causadas por eventos convectivos
  locais (chuvas intensas e curtas sobre uma bacia específica). ERA5 a 10 km de grade
  suaviza esses eventos — o pico de precipitação que o CEMADEN registra em 1–3 estações
  ao redor de um ponto de inundação simplesmente não aparece no ERA5 com a mesma
  magnitude. Isso é uma limitação física, não de modelagem.

= Recomendações

#table(
  columns: (auto, auto),
  stroke: 0.5pt,
  fill: (col, row) => if row == 0 { luma(230) } else { none },
  [*Cenário*], [*Recomendação*],
  [Fonte primária de precipitação (treino e produção)],
    [*Manter CEMADEN.* ERA5 e forecasts não substituem — queda de F2 de ~0.55 para ~0.09. O sinal local dos pluviômetros é insubstituível.],
  [ERA5 como feature complementar],
    [Adicionar ERA5 (temperatura, umidade, pressão) como features auxiliares ao modelo V4/V5b. Não substituir precipitação, mas enriquecer contexto meteorológico sinótico.],
  [Forecast em produção],
    [Para inferência real (D+1), usar CEMADEN das últimas 72h (observado) + forecast de precipitação apenas como feature extra de "chuva prevista". Não substituir acumulados históricos.],
  [Integração Fase 6],
    [Construir feature `precip_prevista_24h` (ERA5 ou forecast API) e adicionar ao pipeline. Avaliar ganho de F2 marginal antes de investir em coleta de forecasts históricos (NOAA GFS).],
)

= Próximos passos (Fase 6)

+ *Adicionar ERA5 como feature ao pipeline* de modelagem atual (V4/V5b): acumulado 24h, 48h, temperatura e umidade relativa. Avaliar ganho de F2 antes de investir em forecasts reais.
+ *Definir lead time de produção*: qual antecedência é operacionalmente útil para a Defesa Civil? Se D+1 (24h), o modelo pode ser re-rodado a cada manhã.
+ *Construir dataset de validação de produção*: cruzar forecasts arquivados do TomorrowIO (nov/2023–mar/2024) com chamados do CEMADEN. Medir degradação de F2 vs baseline ERA5.
+ *Avaliar NOAA GFS* somente se o ganho de F2 no passo 1 for substancial e a degradação no passo 3 for > 10% relativo.

#v(1em)
#line(length: 100%)
#text(size: 8pt, fill: gray)[
  Gerado em: 2026-04-29 | Fonte: TomorrowIO (nov/2023–mar/2024), ERA5 Open-Meteo, CEMADEN Tamanduateí |
  Scripts: `dados/openweater/` | Período de análise: 2023-11-22 → 2024-03-09 (109 dias)
]
