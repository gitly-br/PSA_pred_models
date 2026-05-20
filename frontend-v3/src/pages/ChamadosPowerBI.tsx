import { useEffect, useState } from 'react';
import { ExternalLink, Loader2 } from 'lucide-react';
import { APP_CONFIG } from '@/config/app';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ChamadosOccurrencesProvider,
  useChamadosOccurrences,
} from '@/contexts/ChamadosOccurrencesContext';
import ChamadosDataView from '@/components/chamados/ChamadosDataView';
import ChamadosCompareView from '@/components/chamados/ChamadosCompareView';

function PowerBiEmbed() {
  const [isLoading, setIsLoading] = useState(true);
  const [showFallback, setShowFallback] = useState(false);
  const chamadosUrl = APP_CONFIG.CHAMADOS_IFRAME_URL;

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      if (isLoading) setShowFallback(true);
    }, 8000);

    return () => window.clearTimeout(timeout);
  }, [isLoading]);

  return (
    <div className="rounded-xl border border-border shadow-sm overflow-hidden bg-card">
      <div className="px-4 py-2 border-b border-border flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">
          Fonte: Dados Defesa Civil (Power BI)
        </span>
        <a
          href={chamadosUrl}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-secondary hover:underline inline-flex items-center gap-1"
        >
          Abrir em nova guia
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
      <div className="relative min-h-[70vh] bg-background">
        {isLoading && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-card text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin text-secondary" />
            <p className="text-sm">Carregando painel de chamados...</p>
            {showFallback && (
              <div className="max-w-md space-y-3 text-center">
                <p className="text-xs">
                  O Power BI pode bloquear a visualização incorporada em alguns navegadores ou redes.
                </p>
                <Button asChild variant="secondary" size="sm">
                  <a href={chamadosUrl} target="_blank" rel="noreferrer">
                    Abrir painel em nova guia
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </Button>
              </div>
            )}
          </div>
        )}
        <iframe
          src={chamadosUrl}
          title="Painel de Chamados"
          className="absolute inset-0 h-full w-full border-0"
          loading="lazy"
          allow="fullscreen; clipboard-read; clipboard-write"
          onLoad={() => setIsLoading(false)}
          allowFullScreen
        />
      </div>
    </div>
  );
}

function ChamadosLoadingState() {
  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-6">
      <div className="flex items-center gap-3 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin text-secondary shrink-0" />
        <div>
          <p className="text-sm font-medium text-foreground">Carregando chamados de hoje…</p>
          <p className="text-xs mt-0.5">
            Buscando apenas ocorrências do dia atual para carregar mais rápido.
          </p>
        </div>
      </div>
      <Skeleton className="h-16" />
      <Skeleton className="h-[400px]" />
    </div>
  );
}

function ChamadosErrorState({
  error,
  sourceHint,
  onRetry,
}: {
  error: string;
  sourceHint: string | null;
  onRetry: () => void;
}) {
  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 space-y-3">
      <p className="text-sm text-destructive">{error}</p>
      {sourceHint && <p className="text-xs text-destructive/80">{sourceHint}</p>}
      <Button variant="outline" size="sm" onClick={onRetry}>
        Tentar novamente
      </Button>
    </div>
  );
}

function ChamadosTabs() {
  const { loading, error, sourceHint, reload, loadMeta, loadedRange, refetching } = useChamadosOccurrences();
  const [tab, setTab] = useState('dados');

  if (loading) {
    return <ChamadosLoadingState />;
  }

  if (error) {
    return (
      <ChamadosErrorState error={error} sourceHint={sourceHint} onRetry={reload} />
    );
  }

  return (
    <Tabs value={tab} onValueChange={setTab} className="space-y-4">
      <TabsList className="flex h-auto flex-wrap gap-1">
        <TabsTrigger value="dados" className="text-xs sm:text-sm">
          Mapa e dados
        </TabsTrigger>
        <TabsTrigger value="comparar" className="text-xs sm:text-sm">
          Comparar datas
        </TabsTrigger>
        <TabsTrigger value="powerbi" className="text-xs sm:text-sm">
          Painel Power BI
        </TabsTrigger>
      </TabsList>

      {(loadMeta?.returned ?? 0) > 0 && loadedRange && (
        <p className="text-xs text-muted-foreground">
          {loadMeta!.returned.toLocaleString('pt-BR')} ocorrências
          {loadedRange.date_start === loadedRange.date_end
            ? ` em ${loadedRange.date_start}`
            : ` (${loadedRange.date_start} a ${loadedRange.date_end})`}
          {refetching && ' — atualizando…'}
        </p>
      )}

      <TabsContent value="dados" className="mt-0">
        {tab === 'dados' && <ChamadosDataView />}
      </TabsContent>

      <TabsContent value="comparar" className="mt-0">
        {tab === 'comparar' && <ChamadosCompareView />}
      </TabsContent>

      <TabsContent value="powerbi" className="mt-0">
        {tab === 'powerbi' && <PowerBiEmbed />}
      </TabsContent>
    </Tabs>
  );
}

export default function ChamadosPowerBI() {
  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-heading font-bold text-primary">
            Chamados
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Ocorrências da Defesa Civil: mapa, comparação por datas e painel Power BI.
          </p>
        </div>
        {APP_CONFIG.USE_MOCK_DATA ? (
          <Badge variant="outline" className="w-fit border-amber-500/50 text-amber-700 dark:text-amber-400">
            Dados simulados
          </Badge>
        ) : (
          <Badge variant="outline" className="w-fit border-secondary/50 text-secondary">
            Dados reais (API)
          </Badge>
        )}
      </div>

      <ChamadosOccurrencesProvider>
        <ChamadosTabs />
      </ChamadosOccurrencesProvider>
    </div>
  );
}
