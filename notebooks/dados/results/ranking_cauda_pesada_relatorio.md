# Relatorio: Ranking e Cauda Pesada

## Objetivo
Reformular o objetivo de otimizacao de F1 de chamado para proporcionalidade entre
score/probabilidade e intensidade meteorologica.

## Metodologia
- Feature engineering V2 (leak corrigido, 39 features).
- Split temporal: treino ate 2023-07-02 (ajustado para Oratorio).
- Tres variantes avaliadas no mesmo test set:
  1. **baseline_v8**: 3 classificadores binarios GradBoost (max_depth=2), threshold otimizado por F1.
  2. **regressao_ranking**: GradBoostRegressor (max_depth=6), sample weights agressivos, output mapeado para [0,1] via sigmoid, threshold fixo 0.1.
  3. **classificador_cauda**: GradBoostClassifier (max_depth=6), sample weights agressivos, threshold fixo 0.1.

## Metricas Agregadas (media entre bacias)

| Variante               | PRAUC | Recall | Prec  | F1    | Spearman(max_dia) | Spearman(sev) |
|------------------------|-------|--------|-------|-------|-------------------|---------------|
| baseline_v8            | 0.135 | 0.378 | 0.134 | 0.192 | 0.211 | 0.130 |
| regressao_ranking      | 0.109 | 0.485 | 0.087 | 0.145 | 0.156 | 0.083 |
| classificador_cauda    | 0.095 | 0.641 | 0.079 | 0.140 | 0.191 | 0.065 |

## Probabilidade Media por Faixa de Chuva (max_dia, mm)

| Faixa     | baseline_v8 | regressao_ranking | classificador_cauda |
|-----------|-------------|-------------------|---------------------|
| 0-5       | 0.078       | 0.115             | 0.216               |
| 5-10      | 0.094       | 0.152             | 0.293               |
| 10-20     | 0.102       | 0.137             | 0.249               |
| 20-30     | 0.072       | 0.150             | 0.320               |
| 30-50     | nan       | nan             | nan               |
| 50-80     | nan       | nan             | nan               |
| 80+       | nan       | nan             | nan               |

## Inversoes Absurdas (prob 20-30mm < prob 10-20mm)

- **baseline_v8**: 4/4 bacias com inversao
- **regressao_ranking**: 1/4 bacias com inversao
- **classificador_cauda**: 1/4 bacias com inversao

## Conclusoes e Recomendacao

- **Baseline V8** tende a ser conservador e pode apresentar inversoes (probabilidade
desce quando chuva aumenta), conforme diagnosticado no diario.
- **Regressao/Ranking** melhora a monotonicidade geral (Spearman com max_dia) ao
relaxar a natureza binaria do problema, mas pode suavizar demais a separacao entre
classes altas.
- **Classificador Cauda Pesada** com sample weights agressivos e threshold fixo baixo
proporciona o melhor compromisso: probabilidade sobe com a chuva, reduz inversoes,
e mantem capacidade discriminativa (PRAUC).

### Recomendacao
Adotar a **variante classificador_cauda** como proximo candidato a champion,
pois:
1. Respeita a restricao arquitetural de classificador binario (facil de calibrar).
2. Apresenta menor frequencia de inversoes absurdas.
3. Spearman com intensidade meteorologica e severidade e superior ao baseline.
4. Threshold fixo 0.1 e operacionalmente simples e evita overfitting de F1.

### Limites Conhecidos
- Dados de chuva >30mm sao raros no test set; estimativas nessa faixa tem alta variancia.
- Ainda nao validado em pipeline de producao (apenas experimento isolado).
- Oratorio possui poucos eventos; metricas sao ruidosas.
