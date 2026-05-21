# Etapas de Conserto — Frontend Flood Watch Hub

## 1. Campeão municipal errado (backend)

**Problema**: O `proba` do agregado `all` (municipal) fica 0.0 quando todas as bacias têm `predict=0`, mesmo que alguma bacia tenha `proba > 0` individualmente.

**Causa**: `inference_writer.py` — a seleção do vencedor filtra por `severity > 0`; quando todas são zero, o else zera a proba.

**Correção**: Calcular `all.proba = max(proba de todas as bacias)` mesmo quando `predict` é zero.

## 2. Escala de cores dos períodos (frontend)

**Problema**: `rain_today` devolve milímetros (ex: 4.9), mas o transformer `clamp01()` espera 0~1, saturando tudo em 1.0 (vermelho máximo).

**Causa**: O backend capa em mm (4.9/9.9/14.9), o frontend trata como probabilidade.

**Correção**: No adapter `api.ts`, dividir cada período pelo cap correspondente à cor do dia (4.9 pra verde, 9.9 pra amarelo, 14.9 pra vermelho) para normalizar em 0~1.

## 3. Date Picker sem pré-carga (frontend)

**Problema**: Mudar de mês já dispara predição no dia equivalente. O usuário quer navegar sem disparar.

**Correção**: Separar a seleção visual do gatilho de fetch. Ou adiar o fetch para um botão "Carregar" explícito, ou usar debounce.
