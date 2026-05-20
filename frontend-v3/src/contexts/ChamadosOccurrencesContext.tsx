import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { api, ApiRequestError } from '@/services/api';
import type { Occurrence } from '@/services/mockData';
import { bairroStatsFromOccurrences } from '@/lib/occurrenceFilters';
import { getTodayIso, rangesEqual, type IsoDateRange } from '@/lib/chamadosDates';

export interface ChamadosLoadMeta {
  csv_rows: number;
  returned: number;
  skipped_no_coordinates: number;
  source?: string;
  pages_fetched?: number;
  date_start?: string;
  date_end?: string;
}

interface ChamadosOccurrencesContextValue {
  occurrences: Occurrence[];
  loading: boolean;
  refetching: boolean;
  error: string | null;
  sourceHint: string | null;
  loadMeta: ChamadosLoadMeta | null;
  loadedRange: IsoDateRange | null;
  loadForRange: (range: IsoDateRange) => Promise<void>;
  reload: () => Promise<void>;
}

const ChamadosOccurrencesContext = createContext<ChamadosOccurrencesContextValue | null>(null);

export function ChamadosOccurrencesProvider({ children }: { children: ReactNode }) {
  const [occurrences, setOccurrences] = useState<Occurrence[]>([]);
  const [loading, setLoading] = useState(true);
  const [refetching, setRefetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceHint, setSourceHint] = useState<string | null>(null);
  const [loadMeta, setLoadMeta] = useState<ChamadosLoadMeta | null>(null);
  const [loadedRange, setLoadedRange] = useState<IsoDateRange | null>(null);
  const loadedRangeRef = useRef<IsoDateRange | null>(null);

  const applyError = useCallback(async (err: unknown) => {
    console.error('Failed to load chamados:', err);
    setOccurrences([]);
    setLoadMeta(null);

    let message = 'Não foi possível carregar os chamados.';
    if (err instanceof ApiRequestError) {
      message = err.message;
    } else if (err instanceof DOMException && err.name === 'AbortError') {
      message = 'A requisição expirou. Tente novamente.';
    }

    try {
      const status = await api.getChamadosStatus();
      const parts: string[] = [];
      if (status.power_bi.api) parts.push(status.power_bi.api);
      if (status.power_bi.configured) {
        parts.push(
          status.power_bi.reachable === false
            ? `API Power BI inacessível: ${status.power_bi.reachability_error ?? 'erro de rede'}`
            : 'API Power BI configurada e acessível.',
        );
      }
      setSourceHint(parts.join(' '));
    } catch {
      setSourceHint('Os dados vêm da API pública do Power BI (mesmo relatório do iframe).');
    }

    setError(message);
  }, []);

  const loadForRange = useCallback(async (range: IsoDateRange) => {
    const { dateStart, dateEnd } = range;
    if (!dateStart || !dateEnd) return;

    if (rangesEqual(loadedRangeRef.current, range)) {
      return;
    }

    const isFirstLoad = loadedRangeRef.current === null;
    if (isFirstLoad) {
      setLoading(true);
    } else {
      setRefetching(true);
    }
    setError(null);
    setSourceHint(null);

    try {
      const { items, meta } = await api.getOccurrencesWithMeta({ dateStart, dateEnd });
      setOccurrences(items);
      setLoadMeta(meta ?? null);
      const nextRange = { dateStart, dateEnd };
      loadedRangeRef.current = nextRange;
      setLoadedRange(nextRange);
    } catch (err) {
      await applyError(err);
    } finally {
      setLoading(false);
      setRefetching(false);
    }
  }, [applyError]);

  useEffect(() => {
    const today = getTodayIso();
    void loadForRange({ dateStart: today, dateEnd: today });
  }, [loadForRange]);

  const reload = useCallback(async () => {
    const today = getTodayIso();
    loadedRangeRef.current = null;
    await loadForRange({ dateStart: today, dateEnd: today });
  }, [loadForRange]);

  const value = useMemo(
    () => ({
      occurrences,
      loading,
      refetching,
      error,
      sourceHint,
      loadMeta,
      loadedRange,
      loadForRange,
      reload,
    }),
    [occurrences, loading, refetching, error, sourceHint, loadMeta, loadedRange, loadForRange, reload],
  );

  return (
    <ChamadosOccurrencesContext.Provider value={value}>
      {children}
    </ChamadosOccurrencesContext.Provider>
  );
}

export function useChamadosOccurrences() {
  const ctx = useContext(ChamadosOccurrencesContext);
  if (!ctx) {
    throw new Error('useChamadosOccurrences must be used within ChamadosOccurrencesProvider');
  }
  return ctx;
}

/** Estatísticas por bairro derivadas da lista (para gráficos). */
export function useBairroStats(occurrences: Occurrence[]) {
  return useMemo(() => bairroStatsFromOccurrences(occurrences), [occurrences]);
}
