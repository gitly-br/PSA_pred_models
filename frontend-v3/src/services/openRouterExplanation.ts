export interface OpenRouterExplainResult {
  analise_completa: string;
  headline: string;
}

const STORAGE_PREFIX = 'psa-openrouter-explain-v1:';

function storageKey(cacheDateIso: string, cacheScope = 'default'): string {
  return `${STORAGE_PREFIX}${cacheScope}:${cacheDateIso}`;
}

export function readCachedExplanation(
  cacheDateIso: string,
  cacheScope?: string,
): OpenRouterExplainResult | null {
  try {
    const raw = localStorage.getItem(storageKey(cacheDateIso, cacheScope));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as OpenRouterExplainResult;
    if (parsed?.headline && parsed?.analise_completa) return parsed;
    return null;
  } catch {
    return null;
  }
}

export function writeCachedExplanation(
  cacheDateIso: string,
  value: OpenRouterExplainResult,
  cacheScope?: string,
): void {
  try {
    localStorage.setItem(storageKey(cacheDateIso, cacheScope), JSON.stringify(value));
  } catch {
    // quota / private mode
  }
}

function buildUserPrompt(params: {
  regiao: string;
  data: string;
  proba01: number;
  explanationPipeline: string;
  fatoresSimples: string;
}): string {
  return `Região: ${params.regiao}
Data: ${params.data}
Probabilidade de risco entre 0 e 1: ${params.proba01}

Texto preliminar do sistema, se existir:
${params.explanationPipeline || '(vazio)'}

Fatores que influenciaram o resultado, em ordem aproximada de importância:
${params.fatoresSimples}

Sinal dos fatores:

* Valores positivos aumentaram o risco.
* Valores negativos reduziram o risco.
* Use isso apenas para explicar direção da análise, sem citar números internos.

Formato obrigatório de saída:
{
"analise_completa": "...",
"headline": "..."
}`;
}

const SYSTEM_PROMPT = `Você é um sistema de apoio à decisão para equipes da Defesa Civil.

Sua tarefa é gerar duas explicações sobre o risco de alagamento/inundação:

1. Uma análise operacional completa.
2. Uma frase extremamente curta no formato de manchete/resumo rápido para dashboards e alertas.

Público-alvo: equipe da Defesa Civil sem formação em IA, estatística ou ciência de dados.

Regras obrigatórias:

* Retorne APENAS um JSON válido.
* Não use markdown.
* Não adicione comentários fora do JSON.
* O JSON deve conter exatamente os campos:

  * "analise_completa"
  * "headline"

Regras para "analise_completa":

* Explicar a probabilidade estimada em percentual simples.
* Explicar os principais fatores que aumentaram o risco.
* Explicar os fatores que ajudaram a reduzir o risco, quando existirem.
* Traduzir os fatores para linguagem cotidiana.
* Não citar nomes técnicos, variáveis, SHAP ou colunas internas.
* Não inventar fenômenos ou impactos.
* Priorizar fatores mais relevantes.
* Tom calmo, direto e operacional.
* Máximo de 4 frases curtas.
* Encerrar sugerindo uma ação operacional simples, como manter monitoramento, reforçar atenção ou reduzir estado de alerta.

Regras para "headline":

* Deve ter no máximo 12 palavras.
* Deve funcionar como título rápido de dashboard operacional.
* Não repetir toda a explicação.
* Deve resumir apenas o cenário principal.
* Linguagem extremamente direta.
* Exemplos:

  * "Risco moderado com chuva prevista à tarde"
  * "Baixa probabilidade de alagamento hoje"
  * "Atenção para acúmulo de água no período da tarde"
  * "Monitoramento recomendado em áreas críticas"`;

function extractJsonObject(content: string): string {
  const trimmed = content.trim();
  const fenced = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const candidate = fenced ? fenced[1].trim() : trimmed;
  const start = candidate.indexOf('{');
  const end = candidate.lastIndexOf('}');
  if (start === -1 || end === -1 || end <= start) throw new Error('JSON não encontrado na resposta');
  return candidate.slice(start, end + 1);
}

export async function fetchOpenRouterExplanation(params: {
  regiao: string;
  data: string;
  proba01: number;
  explanationPipeline: string;
  fatoresSimples: string;
  apiKey: string;
  model: string;
  signal?: AbortSignal;
}): Promise<OpenRouterExplainResult> {
  const userContent = buildUserPrompt({
    regiao: params.regiao,
    data: params.data,
    proba01: params.proba01,
    explanationPipeline: params.explanationPipeline,
    fatoresSimples: params.fatoresSimples,
  });

  const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${params.apiKey}`,
      'Content-Type': 'application/json',
      ...(import.meta.env.VITE_OPENROUTER_HTTP_REFERER
        ? { 'HTTP-Referer': import.meta.env.VITE_OPENROUTER_HTTP_REFERER }
        : {}),
      ...(import.meta.env.VITE_OPENROUTER_APP_TITLE
        ? { 'X-Title': import.meta.env.VITE_OPENROUTER_APP_TITLE }
        : {}),
    },
    body: JSON.stringify({
      model: params.model,
      temperature: 0.35,
      messages: [
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content: userContent },
      ],
    }),
    signal: params.signal,
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => '');
    throw new Error(`OpenRouter ${res.status}: ${errText.slice(0, 200)}`);
  }

  const body = (await res.json()) as {
    choices?: { message?: { content?: string } }[];
  };
  const content = body.choices?.[0]?.message?.content;
  if (!content || typeof content !== 'string') {
    throw new Error('Resposta OpenRouter sem conteúdo');
  }

  const jsonStr = extractJsonObject(content);
  const parsed = JSON.parse(jsonStr) as OpenRouterExplainResult;
  if (!parsed.headline || !parsed.analise_completa) {
    throw new Error('JSON sem headline ou analise_completa');
  }
  return {
    headline: String(parsed.headline).trim(),
    analise_completa: String(parsed.analise_completa).trim(),
  };
}
