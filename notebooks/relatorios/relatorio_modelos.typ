#set document(
  title: "Predição de Enchentes por Bacia — Avaliação Técnica",
  author: "Projeto PSA",
)

#set page(
  paper: "a4",
  margin: (x: 2.2cm, y: 2.4cm),
  numbering: "1",
  number-align: center,
  header: context {
    if counter(page).get().first() > 1 [
      #set text(size: 9pt, fill: gray)
      Predição de Enchentes — Santo André · #h(1fr) Avaliação Técnica
      #line(length: 100%, stroke: 0.4pt + gray)
    ]
  },
)

#set text(font: "Liberation Sans", size: 10.5pt, lang: "pt", region: "br")
#set par(justify: true, leading: 0.7em)

#show heading.where(level: 1): it => block(below: 0.8em, above: 1.4em)[
  #set text(size: 16pt, weight: "bold")
  #it.body
  #v(-0.4em)
  #line(length: 100%, stroke: 0.6pt)
]
#show heading.where(level: 2): it => block(below: 0.5em, above: 1em)[
  #set text(size: 13pt, weight: "bold")
  #it
]
#show heading.where(level: 3): it => block(below: 0.3em, above: 0.7em)[
  #set text(size: 11pt, weight: "bold", style: "italic")
  #it
]

#show table.cell.where(y: 0): it => strong(it)
#set table(
  stroke: (x, y) => if y == 0 { (bottom: 0.7pt + black) } else { (bottom: 0.2pt + gray) },
  inset: 7pt,
  align: (x, y) => if x == 0 { left } else { center },
)

// Capa
#align(center)[
  #v(2.5cm)
  #text(size: 22pt, weight: "bold")[Predição de Enchentes por Bacia Hidrográfica]
  #v(0.4cm)
  #text(size: 14pt)[Avaliação técnica dos modelos para uso pela Defesa Civil de Santo André]
  #v(2cm)
  #box(stroke: 0.5pt, inset: 14pt, radius: 4pt)[
    #set text(size: 10.5pt)
    #align(left)[
      *Escopo:* iterações V3 a V7 sobre o pipeline de modelagem. \
      *Bacias avaliadas:* Guarará, Meninos, Oratório, Tamanduateí. \
      *Período de teste:* julho/2023 a 2025. \
      *Status atual:* modelos prontos como apoio à decisão; *não automatização*.
    ]
  ]
  #v(1fr)
  #text(fill: gray)[Documento técnico-executivo · 2026-04-29]
]

#pagebreak()

= Sumário executivo

Foram desenvolvidos modelos de aprendizado de máquina por bacia hidrográfica para predizer ocorrência de enchentes em Santo André. Após cinco iterações com avaliação rigorosa, o modelo champion atual *detecta entre 76% e 91% dos eventos confirmados em cada bacia*, com volume de alarmes operacionalmente compatível (entre 1,3 e 2,5 alarmes/mês na temporada chuvosa).

A avaliação técnica revelou um *teto informacional intransponível com os dados atuais*: o modelo não consegue distinguir consistentemente um evento leve (1 chamado) de um evento grave (5+ chamados), porque a chuva nos dois casos é estatisticamente idêntica. A diferença está em fatores estruturais (drenagem, piscinões) e comportamentais (engajamento por bairro, hora do dia) que não estão capturados nas séries pluviométricas.

#block(fill: rgb("#fff5e0"), inset: 12pt, radius: 4pt, width: 100%)[
  *Recomendação operacional:* o modelo deve ser usado como *apoio à decisão*, não como gatilho automático. Sua função é *priorizar atenção* — flagar dias de risco para que a equipe da defesa civil reforce monitoramento em campo, não substituir essa observação.
]

= Contexto do problema

Santo André, no ABC paulista, sofre alagamentos recorrentes em quatro bacias hidrográficas mapeadas: Guarará, Meninos, Oratório e Tamanduateí. A defesa civil opera reativamente — recebe chamados pela central 156 e despacha equipes. O objetivo deste trabalho é *antecipar* dias de risco usando dados pluviométricos do CEMADEN.

== Dados disponíveis

#table(
  columns: 2,
  table.header[Fonte][Conteúdo],
  [CEMADEN], [5,2 milhões de leituras horárias de pluviômetros (2016–2025), 65 estações nos quatro municípios da região (Santo André, São Bernardo, São Caetano, Mauá).],
  [Chamados 156], [65 mil chamados (2003–2025) classificados como 809.x (alagamentos). Após filtragem e validação, 1.546 chamados confirmados por chuva e mapeados a bacia.],
  [Fontes externas], [79 datas de alagamentos confirmados em jornais e relatórios técnicos, com flags por bacia (#emph[alagamentos_bacias.csv]).],
  [Geometria], [Bairros mapeados a bacias; piscinões com capacidade (sem coordenadas precisas).],
)

== Restrições do problema

- *Dados desbalanceados:* na média, ~5% dos dias da temporada chuvosa têm evento — nas bacias menores (Meninos, Oratório), apenas 24 a 38 eventos confirmados em todo o histórico.
- *Janela de operação:* defesa civil opera com horizonte de 24–48 h. Não há sentido em predizer 30 dias à frente.
- *Custo assimétrico:* perder um evento grave é mais caro que disparar um alarme falso, mas o orçamento de atenção é finito (~3–4 alarmes/mês na temporada chuvosa).

= Métodos

== Pipeline geral

Cada iteração segue o mesmo esqueleto:

1. *Validação de chamados:* cada chamado de alagamento é validado contra a série pluviométrica das estações da própria bacia. Janelas testadas: 1, 3, 6, 24, 48 e 72 h retroativas. Limiares (mm) calibrados por janela. Chamados sem chuva confirmada na bacia são descartados.
2. *Construção de features:* agregações diárias da chuva por bacia (máximo, média, desvio entre estações, número de estações chovendo, picos, índice de precipitação antecedente API).
3. *Split temporal:* treino até julho/2023, teste de julho/2023 a 2025. Filtro sazonal de meses chuvosos (novembro a abril).
4. *Modelagem por bacia:* um modelo independente por bacia (preserva granularidade para a defesa civil). Champion: Gradient Boosting Classifier regularizado (`max_depth=2`, `min_samples_leaf=10`, `subsample=0.8`).

== Avaliação rigorosa

Implementadas para evitar resultados otimistas e mensurar incerteza honestamente:

- *Walk-forward Cross-Validation* (`TimeSeriesSplit` com 5 splits) no treino para escolher o limiar de decisão. O limiar é *fixado antes do test* — sem vazamento.
- *Otimização por F1*, não F2 (priorizar F2 leva o modelo a alarmes excessivos).
- *Bootstrap estratificado* (1000 reamostragens) para intervalo de confiança de 95% sobre as métricas pontuais.
- *Métrica operacional:* alarmes/mês e fração de eventos capturados.

= Iterações realizadas

#table(
  columns: (auto, auto, 1fr),
  table.header[Iteração][Foco][Mudança principal],
  [V3], [Avaliação honesta], [Removido vazamento de threshold; bootstrap de IC95.],
  [V4], [Features], [27 features (vs 16 antes): variabilidade espacial entre estações, regime de intensidade, sazonalidade cíclica, três constantes de saturação API.],
  [V5], [Target enriquecido], [+79 positivos novos via fontes externas (alagamentos\_bacias.csv).],
  [V5b], [Pesagem de positivos], [Eventos só-fonte-externa pesam 0,5; chamados confirmados pesam 1,0.],
  [V6], [Granularidade horária], [Janela 48h em grade de 6h. *Falhou:* autocorrelação alta gerou alarmes contínuos. Abandonado.],
  [V7], [Severidade ordinal], [Target em quatro níveis (0–3). Três classificadores binários ordinais.],
)

== Iteração intermediária — Bacia Meninos

Diagnóstico programático identificou que a bacia Meninos tinha cobertura limitada de estações. Adicionada a estação Vila Vitória (São Bernardo, 7,8 km do centróide), elevando cobertura de 81% para 92% dos chamados (+20 chamados confirmados). Aceito o risco de captar chuva remota em troca de mais positivos para treinar.

= Resultados consolidados

== Modelo champion atual (V7 — severidade ordinal por bacia)

#table(
  columns: 6,
  table.header[Bacia][Eventos no test][Recall global][Recall graves][Alarmes/mês ≥1][Alarmes/mês ≥3],
  [Guarará], [38], [82%], [40% (2/5)], [3,8], [2,2],
  [Meninos], [10], [80%], [s/dados], [1,3], [0,0],
  [Oratório], [23], [91%], [s/dados], [2,5], [0,0],
  [Tamanduateí], [37], [76%], [57% (4/7)], [3,9], [1,7],
)

#text(size: 9pt, fill: gray)[Recall graves: somente Guarará e Tamanduateí têm eventos de severidade 3 no período de teste.]

== Tabela detalhada de detecção (Tamanduateí, V7 GradBoost)

A tabela abaixo é o formato canônico para uso pela defesa civil — mostra, para cada classe real de evento, em qual nível o modelo disparou alarme.

#table(
  columns: 5,
  align: center,
  table.header[Severidade real][N° dias][Detectados ≥1][Detectados ≥2][Detectados ≥3],
  [0 (sem evento)], [387], [26 (FP)], [16], [8],
  [1 (leve)], [27], [21 (78%)], [12], [11],
  [2 (moderado)], [3], [2/3], [2/3], [1/3],
  [3 (grave)], [7], [*5/7 (71%)*], [*4/7 (57%)*], [*4/7 (57%)*],
)

#text(size: 9pt, fill: gray)[Cada coluna é cumulativa: "Detectados ≥2" inclui também os detectados como ≥3.]

== Evolução das iterações

#table(
  columns: 5,
  table.header[Bacia][V3 (honesto)][V4 (features)][V5-F1 (target+)][V7 (ordinal, recall global)],
  [Guarará], [F2 = 0,27], [F2 = 0,43], [F2 = 0,49], [82%],
  [Meninos], [F2 = 0,31], [F2 = 0,59 *(IC largo)*], [F2 = 0,46], [80%],
  [Oratório], [F2 = 0,35], [F2 = 0,47], [F2 = 0,48], [91%],
  [Tamanduateí], [F2 = 0,48], [F2 = 0,58], [F2 = 0,45], [76%],
)

#text(size: 9pt, fill: gray)[F2: pondera recall sobre precisão (β=2). V3–V5b reportados em F2 binário; V7 em recall global por causa do target ordinal.]

= Limitação fundamental — teto informacional

Análise diagnóstica dos casos em que o modelo dispara alarme grave (≥3) sem evento grave correspondente revelou um padrão consistente.

#block(fill: rgb("#ffe8e8"), inset: 12pt, radius: 4pt, width: 100%)[
  *Achado crítico:* em 65–72% dos "falsos alarmes graves", o dia *teve* evento, apenas com severidade menor (1 chamado em vez de 5+). Em apenas 28–35% dos casos não houve nenhum chamado.
]

#table(
  columns: 4,
  table.header[Bacia][Total alarmes ≥3 falsos][Eram eventos sev 1–2][Sem evento (sev=0)],
  [Guarará], [29], [21 (72%)], [8 (28%)],
  [Tamanduateí], [20], [13 (65%)], [7 (35%)],
)

A chuva nesses dias é *estatisticamente idêntica* à dos eventos graves reais:

#table(
  columns: 3,
  table.header[Bacia][Chuva máxima média — falsos alarmes ≥3][Chuva máxima média — eventos sev=3 reais],
  [Guarará], [9,9 mm], [11,3 mm],
  [Tamanduateí], [12,6 mm], [11,4 mm],
)

== Implicação

A diferença entre "1 chamado" e "5+ chamados" não está na pluviometria. Está em:

- *Estrutural:* estado dos piscinões antes do evento, drenagem específica do bairro afetado, ponto exato onde caiu a chuva dentro da bacia.
- *Comportamental:* presença de moradores em casa para ligar (fim de semana × dia útil; hora da chuva), engajamento histórico do bairro com canal de chamados.
- *Viés do label:* chamados são *medida* de enchente, não enchente. Um alagamento sem testemunha não vira chamado.

Esticar o modelo com mais features pluviométricas, calibração ou ensemble *não vai resolver* esse teto.

= Avaliação para sistema crítico

Para que um sistema deste tipo seja confiável o suficiente para ser usado por defesa civil, vale checar honestamente cada dimensão de qualidade.

#table(
  columns: (auto, 1fr, auto),
  table.header[Dimensão][Avaliação][Status],
  [Cobertura de eventos], [76–91% dos eventos confirmados são detectados em alguma bacia.], [✓ Aceitável],
  [Volume de alarmes], [1,3–3,9 alarmes/mês — compatível com orçamento operacional sugerido.], [✓ Aceitável],
  [Diferenciação grave vs leve], [Modelo *não distingue* graus dentro de "dia com risco". Acerta ocorrência, não severidade.], [⚠ Limitado],
  [Confiabilidade estatística], [Bacias menores (Meninos, Oratório) têm intervalos de confiança largos por escassez de dados.], [⚠ Limitado],
  [Antecedência], [Modelo opera sobre chuva já caída (lag-based). Sem dados de previsão, não há antecedência verdadeira.], [⚠ Crítico],
  [Reprodutibilidade], [Pipeline auditável (Polars + scikit-learn), splits e seeds fixos, métricas com IC95.], [✓ Aceitável],
  [Robustez a viés temporal], [Walk-forward CV, sem vazamento de teste. Mas eventos de fontes externas concentrados em datas com cobertura midiática.], [⚠ Limitado],
  [Falsos negativos], [Modelo perde 9–24% dos eventos. Modo de falha investigado caso a caso.], [⚠ Limitado],
  [Comportamento em bordas], [Bacia Meninos sem nenhum evento grave no test — desempenho extrapolado.], [⚠ Crítico],
)

== Limitações que impedem uso autônomo

1. *Sem dados de previsão de chuva*, o modelo enxerga apenas o que já caiu. A função "alarme antecipado" só existe na medida em que a chuva atual prediz a chuva das próximas horas — uma dinâmica meteorológica frágil em sistemas convectivos típicos do verão paulista.
2. *Diferenciação de severidade não é confiável.* Um alarme nível 3 do modelo carrega informação real (eventos graves disparam mais nesse nível), mas a precisão é baixa — apenas 4 dos 24 alarmes ≥3 em Tamanduateí eram realmente graves.
3. *Bacia Meninos com escassez de dados.* Apenas 38 eventos no histórico inteiro; 10 no período de teste. Métricas pontuais aparentemente boas (80% recall) escondem alta variabilidade.
4. *Teto informacional* — descrito acima; mais features pluviométricas não resolvem.

== Recomendações de uso

#block(fill: rgb("#e8f5e9"), inset: 12pt, radius: 4pt, width: 100%)[
  1. *Usar como apoio à decisão*, não como gatilho automático. O modelo flagra dias com risco; *a equipe valida em campo*.
  2. *Tratar todo alarme como "atenção sugerida"*, sem distinguir nível 1, 2 ou 3 para fins operacionais. A diferenciação é estatisticamente fraca.
  3. *Monitorar mensalmente* o volume de alarmes vs eventos. Drift no comportamento do modelo deve disparar revisão.
  4. *Não usar para Bacia Meninos* sem revalidação — escassez de dados torna o desempenho histórico não generalizável.
  5. *Não substituir o canal 156* — modelo complementa, não substitui, observação em campo e relatos de moradores.
]

= Próximos passos sugeridos

== Para superar o teto informacional

- Investigar *features extra-pluviométricas* já disponíveis: hora do dia da chuva, dia da semana, "alagou nos últimos 7 dias?".
- Buscar *telemetria dos piscinões* (estado de enchimento) — única fonte direta do componente estrutural não capturado hoje.
- Avaliar *granularidade espacial intra-bacia* — alagamentos são em pontos específicos; agregação por bacia inteira pode estar mascarando sinal.

== Para tornar o sistema operacional

- Integrar *previsão de chuva* (Open Weather histórico ou similar) — pré-requisito para antecedência real.
- Implementar *calibração isotônica* das probabilidades para que "60% chance" tenha significado consistente.
- Estabelecer *processo de retreino periódico* (anual ou após cada temporada chuvosa).
- Construir *dashboard operacional* para a defesa civil, com histórico de alarmes vs eventos e capacidade de feedback do operador.

= Conclusão

Os modelos atuais são *operacionalmente úteis como apoio à decisão*: detectam consistentemente os dias de risco, com volume de alarmes administrável. *Não são adequados para automação*: a diferenciação de severidade dentro de "dia com risco" é estatisticamente fraca, e a ausência de dados de previsão limita a antecedência real.

A descoberta mais importante desta sessão de trabalho é o *teto informacional dos dados pluviométricos*: a partir deste ponto, ganhos vão depender de novas fontes de dados (telemetria de piscinões, previsão de chuva, granularidade espacial) ou de mudanças no recorte do problema, não de mais ajuste fino dos modelos atuais.
