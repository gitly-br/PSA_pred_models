import { useEffect, useState } from 'react';
import { HelpCircle } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import type { PredictionDay } from '@/services/mockData';
import {
  fetchOpenRouterExplanation,
  readCachedExplanation,
  writeCachedExplanation,
} from '@/services/openRouterExplanation';

interface PredictionSummaryProps {
  prediction: PredictionDay;
}

const DEFAULT_MODEL = 'deepseek/deepseek-v4-flash';

export default function PredictionSummary({ prediction }: PredictionSummaryProps) {
  const meta = prediction.explainMeta;
  const apiKeyRaw = import.meta.env.VITE_OPENROUTER_API_KEY;
  const apiKeyCandidate = typeof apiKeyRaw === 'string' ? apiKeyRaw.trim() : '';
  const apiKey = apiKeyCandidate.startsWith('INSIRA_') ? '' : apiKeyCandidate;
  const model =
    typeof import.meta.env.VITE_OPENROUTER_MODEL === 'string' &&
    import.meta.env.VITE_OPENROUTER_MODEL.trim()
      ? import.meta.env.VITE_OPENROUTER_MODEL.trim()
      : DEFAULT_MODEL;

  const useOpenRouter = Boolean(meta && apiKey);

  const [headline, setHeadline] = useState<string | null>(null);
  const [analiseCompleta, setAnaliseCompleta] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    if (!useOpenRouter || !meta) {
      setHeadline(null);
      setAnaliseCompleta(null);
      setLoading(false);
      setFetchError(null);
      return;
    }

    const cached = readCachedExplanation(meta.cacheDateIso, meta.cacheScope);
    if (cached) {
      setHeadline(cached.headline);
      setAnaliseCompleta(cached.analise_completa);
      setLoading(false);
      setFetchError(null);
      return;
    }

    const controller = new AbortController();
    let cancelled = false;

    setHeadline(null);
    setAnaliseCompleta(null);
    setFetchError(null);
    setLoading(true);

    fetchOpenRouterExplanation({
      regiao: meta.regionDisplay,
      data: prediction.date,
      proba01: meta.proba01,
      explanationPipeline: meta.pipelineExplanation,
      fatoresSimples: meta.fatoresSimples,
      apiKey,
      model,
      signal: controller.signal,
    })
      .then(result => {
        if (cancelled) return;
        writeCachedExplanation(meta.cacheDateIso, result, meta.cacheScope);
        setHeadline(result.headline);
        setAnaliseCompleta(result.analise_completa);
      })
      .catch(err => {
        if (cancelled || (err instanceof DOMException && err.name === 'AbortError')) return;
        console.warn('[PredictionSummary] OpenRouter:', err);
        setFetchError('Não foi possível obter a explicação automática agora.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [
    useOpenRouter,
    apiKey,
    model,
    prediction.date,
    meta?.cacheDateIso,
    meta?.cacheScope,
    meta?.regionDisplay,
    meta?.proba01,
    meta?.pipelineExplanation,
    meta?.fatoresSimples,
  ]);

  const getStatusColor = (prob: number) => {
    if (prob < 30) return 'text-safe';
    if (prob < 60) return 'text-moderate';
    return 'text-critical';
  };

  const summaryText = headline ?? prediction.message;

  return (
    <Card className="border border-border shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-heading">
          <span className={cn('text-lg font-bold', getStatusColor(prediction.probability))}>
            {prediction.probability}% de possibilidade
          </span>
          {' '}em {prediction.date}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-start gap-2">
          <p
            className={cn(
              'text-sm text-muted-foreground flex-1 leading-snug',
              !headline && 'italic',
              loading && 'animate-pulse',
            )}
            aria-live={loading ? 'polite' : undefined}
          >
            {summaryText}
          </p>
          {analiseCompleta ? (
            <Dialog>
              <DialogTrigger asChild>
                <button
                  type="button"
                  className="shrink-0 rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label="Ver explicação completa da predição"
                >
                  <HelpCircle className="h-5 w-5" aria-hidden />
                </button>
              </DialogTrigger>
              <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
                <DialogHeader>
                  <DialogTitle>Análise operacional</DialogTitle>
                </DialogHeader>
                <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                  {analiseCompleta}
                </p>
              </DialogContent>
            </Dialog>
          ) : null}
        </div>

        {useOpenRouter && fetchError && !headline && (
          <p className="mt-1 text-xs text-destructive/80">{fetchError}</p>
        )}
      </CardContent>
    </Card>
  );
}
