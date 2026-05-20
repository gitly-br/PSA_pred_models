# Relatorio: Atualizacao de station_ids no MongoDB

- **Data/hora (UTC)**: 2026-05-20T16:27:55.144600+00:00
- **Colecao**: `floodcast.models`
- **URI**: `mongodb://psa:psa@localhost:16521/?authSource=admin`

## Resumo

- Documentos encontrados antes: 4
- Documentos atualizados: 0
- Documentos ja corretos (skipped): 4
- Bacias sem mapping: 0
- Falhas durante update: 0
- Divergencias apos update: 0

## Mapping utilizado (estacoes_bacia.json)

| Bacia | Numero de estacoes |
|-------|-------------------|
| guarara | 17 |
| meninos | 10 |
| oratorio | 11 |
| tamanduatei | 19 |

## Estado antes do update

| name | bacia | active | is_champion | station_ids (count) |
|------|-------|--------|-------------|---------------------|
| champion_guarara | guarara | True | True | 17 |
| champion_oratorio | oratorio | True | True | 11 |
| champion_meninos | meninos | True | True | 10 |
| champion_tamanduatei | tamanduatei | True | True | 19 |

## Estado apos o update

| name | bacia | active | is_champion | station_ids (count) |
|------|-------|--------|-------------|---------------------|
| champion_guarara | guarara | True | True | 17 |
| champion_oratorio | oratorio | True | True | 11 |
| champion_meninos | meninos | True | True | 10 |
| champion_tamanduatei | tamanduatei | True | True | 19 |

## Detalhe das atualizacoes

- **champion_guarara** (guarara): already correct
- **champion_oratorio** (oratorio): already correct
- **champion_meninos** (meninos): already correct
- **champion_tamanduatei** (tamanduatei): already correct

## Verificacao pos-update

Nenhuma divergencia encontrada.
