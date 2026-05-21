import { APP_CONFIG } from '@/config/app';
import { addDays, format } from 'date-fns';
import {
  generatePredictionDays,
  generateBasinPredictions,
  generateWeatherData,
  generateModelDetails,
  generateOccurrences,
  generateBairroStats,
  type PredictionDay,
  type BasinPrediction,
  type WeatherHour,
  type ModelDetail,
  type Occurrence,
  type BairroStat,
} from './mockData';
import type {
  AvailableDatesApiResponse,
  RegionApiResponse,
  RegionDayData,
  RegionAllData,
  RegionBasinData,
  RegionModelEntry,
  ForecastHourlyItem,
} from './apiTypes';
import {
  transformPredictions,
  transformPredictionsFromWeather,
  transformBasinPredictions,
  transformModelDetails,
  transformWeatherData,
} from './apiTransformers';

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

let cachedRegionData: { date: string; data: RegionApiResponse } | null = null;
let cachedForecastData: { date: string; data: ForecastHourlyItem[] } | null = null;
let cachedAvailableDates: string[] | null = null;

const API_TIMEOUT_MS = 30000;
const MOCK_DATE_WINDOW_DAYS = 30;

export class ApiRequestError extends Error {
  status: number;
  body?: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.body = body;
  }
}

async function fetchJson<T>(url: string, options?: { timeoutMs?: number }): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(),
    options?.timeoutMs ?? API_TIMEOUT_MS,
  );

  try {
    const res = await fetch(url, { signal: controller.signal });
    const text = await res.text();
    let body: unknown = undefined;
    if (text) {
      try {
        body = JSON.parse(text) as unknown;
      } catch {
        body = text;
      }
    }

    if (!res.ok) {
      const apiMessage = typeof body === 'object' && body !== null && 'error' in body
        ? String((body as { error: unknown }).error)
        : undefined;
      throw new ApiRequestError(
        apiMessage ?? `API error: ${res.status} ${res.statusText}`,
        res.status,
        body,
      );
    }

    return body as T;
  } finally {
    window.clearTimeout(timeout);
  }
}

function flattenModels(models: unknown): Record<string, RegionModelEntry> | undefined {
  if (!models || typeof models !== 'object') return undefined;
  const flat: Record<string, RegionModelEntry> = {};
  for (const basinModels of Object.values(models as Record<string, unknown>)) {
    if (typeof basinModels !== 'object' || basinModels === null) continue;
    for (const [modelName, modelData] of Object.entries(basinModels as Record<string, unknown>)) {
      if (typeof modelData !== 'object' || modelData === null) continue;
      const md = modelData as Record<string, unknown>;
      flat[modelName] = {
        proba: (md.proba as number) ?? 0,
        predict: md.predict as number | undefined,
        shap: (md.shap as [string, number][] | undefined) ?? (md.shap_explanation as [string, number][] | undefined),
      };
    }
  }
  return Object.keys(flat).length > 0 ? flat : undefined;
}

function buildAllRegionDay(raw: unknown): RegionAllData | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const r = raw as Record<string, unknown>;
  return {
    proba: (r.proba as number) ?? 0,
    rain_today: (r.rain_today as RegionAllData['rain_today']) ?? { night: 0, morning: 0, afternoon: 0, evening: 0 },
    explanation: (r.explanation as string) ?? '',
    models: flattenModels(r.models),
  };
}

function buildBasinDay(raw: unknown): RegionBasinData | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const r = raw as Record<string, unknown>;
  return {
    proba: (r.proba as number) ?? 0,
    models: r.models as RegionBasinData['models'],
  };
}

async function fetchRegionData(date: Date): Promise<RegionApiResponse> {
  const dateStr = format(date, 'yyyy-MM-dd');
  const tomorrowStr = format(addDays(date, 1), 'yyyy-MM-dd');

  if (cachedRegionData && cachedRegionData.date === dateStr) {
    return cachedRegionData.data;
  }

  const base = APP_CONFIG.API_BASE_URL;
  const basinIds = ['tamanduatei', 'guarara', 'oratorio', 'meninos'] as const;

  const [todayAllRaw, tomorrowAllRaw, ...basinRaws] = await Promise.all([
    fetchJson<unknown>(`${base}/region/all?date=${dateStr}`).catch(() => null),
    fetchJson<unknown>(`${base}/region/all?date=${tomorrowStr}`).catch(() => null),
    ...basinIds.map(id =>
      fetchJson<unknown>(`${base}/region/${id}?date=${dateStr}`).catch(() => null),
    ),
  ]);

  const today: RegionDayData = { all: buildAllRegionDay(todayAllRaw) };
  basinIds.forEach((id, i) => {
    const basinRaw = basinRaws[i];
    if (basinRaw) today[id] = buildBasinDay(basinRaw);
  });

  const tomorrow: RegionDayData = { all: buildAllRegionDay(tomorrowAllRaw) };

  const result: RegionApiResponse = { today, tomorrow };
  cachedRegionData = { date: dateStr, data: result };
  return result;
}

async function fetchForecastData(date: Date): Promise<ForecastHourlyItem[]> {
  const dateStr = format(date, 'yyyy-MM-dd');
  if (cachedForecastData && cachedForecastData.date === dateStr) {
    return cachedForecastData.data;
  }

  const url = `${APP_CONFIG.API_BASE_URL}/forecast-data?date=${dateStr}`;
  const data = await fetchJson<ForecastHourlyItem[]>(url);
  cachedForecastData = { date: dateStr, data };
  return data;
}

function dateFromApiDate(value: string): Date {
  return new Date(`${value}T12:00:00`);
}

function getMockAvailableDates(baseDate = new Date()): string[] {
  return Array.from({ length: MOCK_DATE_WINDOW_DAYS * 2 + 1 }, (_, index) =>
    format(addDays(baseDate, index - MOCK_DATE_WINDOW_DAYS), 'yyyy-MM-dd'),
  );
}

async function fetchAvailableDates(): Promise<string[]> {
  if (cachedAvailableDates) {
    return cachedAvailableDates;
  }

  const response = await fetchJson<AvailableDatesApiResponse>(`${APP_CONFIG.API_BASE_URL}/get_dates/`);
  if (!response.success || response.conn_problem) {
    throw new Error(response.err_mg || 'Unable to load available API dates');
  }

  cachedAvailableDates = [...response.dates].sort();
  return cachedAvailableDates;
}

export const api = {
  async getPredictions(date: Date): Promise<PredictionDay[]> {
    if (APP_CONFIG.USE_MOCK_DATA) {
      await delay(300);
      return generatePredictionDays(date);
    }
    try {
      const data = await fetchRegionData(date);
      return transformPredictions(data, date);
    } catch (error) {
      console.warn('Region inference unavailable, using OpenWeather only:', error);
      const hourlyData = await fetchForecastData(date);
      return transformPredictionsFromWeather(hourlyData, date);
    }
  },

  async getBasinPredictions(date?: Date): Promise<BasinPrediction[]> {
    if (APP_CONFIG.USE_MOCK_DATA) {
      await delay(400);
      return generateBasinPredictions(date);
    }
    try {
      const data = await fetchRegionData(date ?? new Date());
      return transformBasinPredictions(data);
    } catch (error) {
      console.warn('Basin inference unavailable for selected date:', error);
      return [];
    }
  },

  async getWeatherData(date?: Date): Promise<WeatherHour[]> {
    if (APP_CONFIG.USE_MOCK_DATA) {
      await delay(350);
      return generateWeatherData(date);
    }
    const hourlyData = await fetchForecastData(date ?? new Date());
    return transformWeatherData(hourlyData);
  },

  async getLatestAvailableDate(maxDate = new Date()): Promise<Date | null> {
    if (APP_CONFIG.USE_MOCK_DATA) {
      return maxDate;
    }

    const maxDateStr = format(maxDate, 'yyyy-MM-dd');
    const dates = await fetchAvailableDates();
    const latest = dates.filter(date => date <= maxDateStr).at(-1) ?? dates.at(-1);
    return latest ? dateFromApiDate(latest) : null;
  },

  async getAvailableDates(): Promise<string[]> {
    if (APP_CONFIG.USE_MOCK_DATA) {
      return getMockAvailableDates();
    }

    return fetchAvailableDates();
  },

  async getModelDetails(date?: Date): Promise<ModelDetail[]> {
    if (APP_CONFIG.USE_MOCK_DATA) {
      await delay(300);
      return generateModelDetails();
    }
    const data = await fetchRegionData(date ?? new Date());
    return transformModelDetails(data);
  },

  async getOccurrences(): Promise<Occurrence[]> {
    const { items } = await this.getOccurrencesWithMeta();
    return items;
  },

  async getChamadosStatus(): Promise<{
    ready: boolean;
    mode?: string;
    power_bi: {
      embed: string;
      api?: string;
      configured?: boolean;
      reachable?: boolean;
      reachability_error?: string | null;
      model_id?: number;
    };
    minio: {
      configured: boolean;
      host: string;
      port: string;
      bucket: string;
      object_key: string;
      reachable?: boolean;
      reachability_error?: string | null;
      host_override?: string | null;
    };
    local_csv: { path: string | null; exists: boolean; prefer_local: boolean };
  }> {
    return fetchJson(`${APP_CONFIG.API_BASE_URL}/chamados_pbi/status`, { timeoutMs: 10000 });
  },

  async getOccurrencesWithMeta(params?: {
    dateStart?: string;
    dateEnd?: string;
    date?: 'today';
  }): Promise<{
    items: Occurrence[];
    meta?: {
      csv_rows: number;
      returned: number;
      skipped_no_coordinates: number;
      source?: string;
      pages_fetched?: number;
      date_start?: string;
      date_end?: string;
    };
  }> {
    if (APP_CONFIG.USE_MOCK_DATA) {
      await delay(300);
      const items = generateOccurrences(80);
      return {
        items,
        meta: {
          csv_rows: items.length,
          returned: items.length,
          skipped_no_coordinates: 0,
        },
      };
    }
    const qs = new URLSearchParams();
    if (params?.dateStart) qs.set('date_start', params.dateStart);
    if (params?.dateEnd) qs.set('date_end', params.dateEnd);
    if (!params?.dateStart && !params?.dateEnd) {
      qs.set('date', params?.date ?? 'today');
    }
    const query = qs.toString();
    const url = `${APP_CONFIG.API_BASE_URL}/chamados_pbi/occurrences${query ? `?${query}` : ''}`;
    const data = await fetchJson<Occurrence[] | {
      items: Occurrence[];
      meta?: {
        csv_rows: number;
        returned: number;
        skipped_no_coordinates: number;
        source?: string;
        date_start?: string;
        date_end?: string;
      };
    }>(url, {
      timeoutMs: 45000,
    });
    if (Array.isArray(data)) {
      return { items: data };
    }
    return { items: data.items ?? [], meta: data.meta };
  },

  async getBairroStats(): Promise<BairroStat[]> {
    if (APP_CONFIG.USE_MOCK_DATA) {
      await delay(200);
      return generateBairroStats();
    }
    const occurrences = await this.getOccurrences();
    return occurrences.reduce<BairroStat[]>((stats, occurrence) => {
      const found = stats.find(item => item.name === occurrence.bairro);
      if (found) {
        found.count += 1;
      } else {
        stats.push({ name: occurrence.bairro, count: 1 });
      }
      return stats;
    }, []).sort((a, b) => b.count - a.count);
  },

  clearCache() {
    cachedRegionData = null;
    cachedForecastData = null;
    cachedAvailableDates = null;
  },
};
