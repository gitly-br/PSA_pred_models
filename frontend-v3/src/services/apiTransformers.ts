/**
 * Transforms real API responses into the component-level interfaces
 */
import { format, addDays } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { APP_CONFIG } from '@/config/app';
import { buildFactorsSimpleText, pickPrimaryModelShap } from '@/lib/shapHumanize';
import type {
  RegionApiResponse,
  RegionDayData,
  ForecastHourlyItem,
  RegionModelEntry,
} from './apiTypes';
import type { PredictionDay, BasinPrediction, WeatherHour, ModelDetail } from './mockData';

const BASIN_NAMES: Record<string, string> = {
  tamanduatei: 'Bacia do Tamanduateí Central',
  guarara: 'Sub-bacia do Guarará',
  oratorio: 'Bacia do Oratório',
  meninos: 'Bacia dos Meninos',
};

const REGION_NAMES: Record<string, string> = {
  all: 'Modelos de todo o município',
  tamanduatei: 'Modelos de bacia do Tamanduateí',
  guarara: 'Modelos de sub-bacia do Guarará',
  meninos: 'Modelos de bacia dos Meninos',
  oratorio: 'Modelos de bacia do Oratório',
};

const MODEL_COLORS: string[] = [
  'hsl(142, 60%, 40%)',
  'hsl(80, 60%, 45%)',
  'hsl(0, 60%, 60%)',
  'hsl(38, 92%, 50%)',
  'hsl(200, 60%, 50%)',
];

function clamp01(value: number | null | undefined): number {
  if (value == null || Number.isNaN(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

function weatherRiskFromHours(items: ForecastHourlyItem[]): number {
  if (items.length === 0) return 0;

  const maxPop = Math.max(...items.map(item => item.pop ?? 0));
  const totalRain = items.reduce((sum, item) => sum + (item.rain ?? 0), 0);
  const rainScore = Math.min(1, totalRain / 20);
  return Math.max(maxPop, rainScore);
}

function transformDayPrediction(
  dayData: RegionDayData | undefined,
  date: Date
): PredictionDay {
  const allData = dayData?.all;
  const proba = allData?.proba ?? 0;
  const rainToday = allData?.rain_today;

  const pipelineMsg =
    allData?.explanation ??
    (proba < 0.2
      ? 'Não há precipitação significativa prevista para o período'
      : proba < 0.5
        ? 'Precipitação leve prevista, atenção moderada'
        : 'Alta precipitação prevista, atenção redobrada');

  const shapPairs = pickPrimaryModelShap(allData?.models);
  const fatoresSimples = buildFactorsSimpleText(shapPairs);

  return {
    date: format(date, 'dd/MM/yyyy'),
    dayOfWeek: format(date, 'EEEE', { locale: ptBR }),
    probability: Math.round(proba * 100),
    periods: {
      // API mapping: night→madrugada, morning→manhã, afternoon→tarde, evening→noite
      madrugada: rainToday ? clamp01(rainToday.night) : clamp01(proba),
      manha: rainToday ? clamp01(rainToday.morning) : clamp01(proba),
      tarde: rainToday ? clamp01(rainToday.afternoon) : clamp01(proba),
      noite: rainToday ? clamp01(rainToday.evening) : clamp01(proba),
    },
    message: pipelineMsg,
    explainMeta: {
      cacheDateIso: format(date, 'yyyy-MM-dd'),
      cacheScope: `${APP_CONFIG.REGION_NAME}:all`,
      regionDisplay: APP_CONFIG.CITY_NAME,
      proba01: Math.min(1, Math.max(0, proba)),
      pipelineExplanation: allData?.explanation ?? '',
      fatoresSimples,
    },
  };
}

export function transformPredictions(
  data: RegionApiResponse,
  selectedDate: Date
): PredictionDay[] {
  return [
    transformDayPrediction(data.today, selectedDate),
    transformDayPrediction(data.tomorrow, addDays(selectedDate, 1)),
  ];
}

export function transformPredictionsFromWeather(
  hourlyData: ForecastHourlyItem[],
  selectedDate: Date
): PredictionDay[] {
  return [0, 1].map(dayOffset => {
    const date = addDays(selectedDate, dayOffset);
    const dayHours = hourlyData.slice(dayOffset * 24, (dayOffset + 1) * 24);
    const probability = Math.round(weatherRiskFromHours(dayHours) * 100);
    const totalRain = dayHours.reduce((sum, item) => sum + (item.rain ?? 0), 0);

    return {
      date: format(date, 'dd/MM/yyyy'),
      dayOfWeek: format(date, 'EEEE', { locale: ptBR }),
      probability,
      periods: {
        madrugada: weatherRiskFromHours(dayHours.slice(0, 6)),
        manha: weatherRiskFromHours(dayHours.slice(6, 12)),
        tarde: weatherRiskFromHours(dayHours.slice(12, 18)),
        noite: weatherRiskFromHours(dayHours.slice(18, 24)),
      },
      message:
        totalRain > 0
          ? `Dados OpenWeather disponíveis. Chuva acumulada prevista: ${totalRain.toFixed(1)} mm.`
          : 'Dados OpenWeather disponíveis. Sem chuva acumulada prevista no período.',
    };
  });
}

export function transformBasinPredictions(
  data: RegionApiResponse
): BasinPrediction[] {
  const today = data.today;
  const basinIds = ['tamanduatei', 'guarara', 'oratorio', 'meninos'];

  return basinIds
    .filter(id => today[id] !== undefined)
    .map(id => ({
      id,
      name: BASIN_NAMES[id] || id,
      probability: Math.round(((today[id] as { proba: number })?.proba ?? 0) * 100),
    }));
}

export function transformModelDetails(
  data: RegionApiResponse
): ModelDetail[] {
  const today = data.today;
  const regions = Object.keys(today);

  return regions
    .filter(region => today[region]?.models)
    .map(region => {
      const regionData = today[region]!;
      const models = regionData.models!;

      return {
        regionName: REGION_NAMES[region] || `Modelos de ${region}`,
        models: Object.entries(models).map(([name, modelData], idx) => ({
          name: name.toUpperCase(),
          value: Math.round((modelData as RegionModelEntry).proba * 100),
          color: MODEL_COLORS[idx % MODEL_COLORS.length],
        })),
      };
    });
}

export function transformWeatherData(
  hourlyData: ForecastHourlyItem[]
): WeatherHour[] {
  return hourlyData.slice(0, 24).map((item, i) => ({
    hour: `${String(i).padStart(2, '0')}h`,
    temperature: Math.round(item.temp * 10) / 10,
    precipitation: Math.round((item.rain ?? 0) * 100) / 100,
    probabilityLabel: `${((item.pop ?? 0) * 100).toFixed(0)}%`,
  }));
}
