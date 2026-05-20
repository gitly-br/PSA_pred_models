import { format, addDays } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { buildFactorsSimpleText } from '@/lib/shapHumanize';

/** Metadados para explicação via OpenRouter (API real); opcional no mock */
export interface PredictionExplainMeta {
  /** Chave do dia para cache (YYYY-MM-DD) no localStorage */
  cacheDateIso: string;
  /** Escopo do modelo/previsão para evitar reuso indevido do cache */
  cacheScope: string;
  regionDisplay: string;
  proba01: number;
  pipelineExplanation: string;
  fatoresSimples: string;
}

export interface PredictionDay {
  date: string;
  dayOfWeek: string;
  probability: number;
  periods: {
    madrugada: number;
    manha: number;
    tarde: number;
    noite: number;
  };
  message: string;
  explainMeta?: PredictionExplainMeta;
}

export interface BasinPrediction {
  id: string;
  name: string;
  probability: number;
}

export interface WeatherHour {
  hour: string;
  temperature: number;
  precipitation: number;
  probabilityLabel: string;
}

export interface ModelDetail {
  regionName: string;
  models: { name: string; value: number; color: string }[];
}

export interface Occurrence {
  id: string;
  lat: number;
  lng: number;
  intensity: number;
  bairro: string;
  date: string;
  tipo: string;
  servico?: string;
  interdicao?: boolean;
}

export interface OccurrenceFilters {
  dateStart: string;
  dateEnd: string;
  servico: string;
  bairro: string;
  interdicao: string;
  tipoArea: string;
}

export interface BairroStat {
  name: string;
  count: number;
}

// Deterministic seed-based random for consistent mock data
function seededRandom(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

function seededInt(seed: number, min: number, max: number): number {
  return Math.floor(seededRandom(seed) * (max - min + 1)) + min;
}

function seededSigned(seed: number, minAbs: number, maxAbs: number): number {
  const magnitude = seededRandom(seed) * (maxAbs - minAbs) + minAbs;
  const sign = seededRandom(seed + 97) >= 0.42 ? 1 : -1;
  return Number((magnitude * sign).toFixed(4));
}

function buildMockShapPairs(seed: number, probability: number): [string, number][] {
  const riskBias = probability >= 50 ? 1 : -1;
  return [
    ['rain_sum_12_18', seededSigned(seed + 101, 0.12, 0.36) * riskBias],
    ['pop_12_18', seededSigned(seed + 102, 0.08, 0.24) * riskBias],
    ['humidity_mean_6_12', seededSigned(seed + 103, 0.05, 0.18)],
    ['pressure_mean_0_6', -Math.abs(seededSigned(seed + 104, 0.04, 0.14))],
    ['clouds_mean_12_18', seededSigned(seed + 105, 0.04, 0.12)],
    ['wind_speed_mean_18_24', -Math.abs(seededSigned(seed + 106, 0.03, 0.1))],
  ].sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
}

export function generatePredictionDays(selectedDate: Date): PredictionDay[] {
  const dateSeed = selectedDate.getFullYear() * 10000 + (selectedDate.getMonth() + 1) * 100 + selectedDate.getDate();

  return [0, 1].map(offset => {
    const date = addDays(selectedDate, offset);
    const seed = dateSeed + offset;
    const probability = seededInt(seed, 5, 65);
    const shapPairs = buildMockShapPairs(seed, probability);
    const message = probability < 20
      ? 'Não há precipitação significativa prevista para o período'
      : probability < 50
        ? 'Precipitação leve prevista, atenção moderada'
        : 'Alta precipitação prevista, atenção redobrada';

    return {
      date: format(date, 'dd/MM/yyyy'),
      dayOfWeek: format(date, 'EEEE', { locale: ptBR }),
      probability,
      periods: {
        madrugada: seededInt(seed + 1, 0, probability + 10) / 100,
        manha: seededInt(seed + 2, 0, probability + 10) / 100,
        tarde: seededInt(seed + 3, 0, probability + 10) / 100,
        noite: seededInt(seed + 4, 0, probability + 10) / 100,
      },
      message,
      explainMeta: {
        cacheDateIso: format(date, 'yyyy-MM-dd'),
        cacheScope: `mock:${offset}:santoandre:all`,
        regionDisplay: 'Santo André',
        proba01: probability / 100,
        pipelineExplanation: message,
        fatoresSimples: buildFactorsSimpleText(shapPairs),
      },
    };
  });
}

export function generateBasinPredictions(selectedDate = new Date()): BasinPrediction[] {
  const seed = selectedDate.getFullYear() * 10000 + (selectedDate.getMonth() + 1) * 100 + selectedDate.getDate();

  return [
    { id: 'tamanduatei', name: 'Bacia do Tamanduateí Central', probability: seededInt(seed + 10, 10, 70) },
    { id: 'guarara', name: 'Sub-bacia do Guarará', probability: seededInt(seed + 11, 5, 60) },
    { id: 'oratorio', name: 'Bacia do Oratório', probability: seededInt(seed + 12, 5, 50) },
    { id: 'meninos', name: 'Bacia dos Meninos', probability: seededInt(seed + 13, 10, 55) },
  ];
}

export function generateWeatherData(selectedDate = new Date()): WeatherHour[] {
  const dateSeed = selectedDate.getFullYear() * 10000 + (selectedDate.getMonth() + 1) * 100 + selectedDate.getDate();

  return Array.from({ length: 24 }, (_, i) => {
    const baseTemp = 21 + Math.sin((i - 6) * Math.PI / 12) * 6;
    const temp = Math.round((baseTemp + seededRandom(dateSeed + i + 100) * 2 - 1) * 10) / 10;
    const precip = Math.max(0, Math.round((seededRandom(dateSeed + i + 200) * 0.5 - 0.2) * 100) / 100);
    return {
      hour: `${String(i).padStart(2, '0')}h`,
      temperature: temp,
      precipitation: precip,
      probabilityLabel: `${(precip * 100).toFixed(1)}%`,
    };
  });
}

export function generateModelDetails(): ModelDetail[] {
  const today = new Date();
  const seed = today.getFullYear() * 10000 + (today.getMonth() + 1) * 100 + today.getDate();

  return [
    {
      regionName: 'Modelos de todo o município',
      models: [
        { name: 'XGBOOST_1', value: seededInt(seed + 20, 5, 35), color: 'hsl(142, 60%, 40%)' },
        { name: 'LIGHTGBM_1', value: seededInt(seed + 21, 3, 25), color: 'hsl(80, 60%, 45%)' },
      ],
    },
    {
      regionName: 'Modelos de sub-bacia do Guarará',
      models: [
        { name: 'GBC_1', value: seededInt(seed + 22, 20, 75), color: 'hsl(0, 60%, 60%)' },
      ],
    },
    {
      regionName: 'Modelos de bacia dos Meninos',
      models: [
        { name: 'GBC_1', value: seededInt(seed + 23, 10, 45), color: 'hsl(142, 60%, 40%)' },
      ],
    },
    {
      regionName: 'Modelos de bacia do Oratório',
      models: [
        { name: 'XGBOOST_1', value: seededInt(seed + 24, 5, 20), color: 'hsl(142, 60%, 40%)' },
      ],
    },
    {
      regionName: 'Modelos de bacia do Tamanduateí',
      models: [
        { name: 'XGBOOST_1', value: seededInt(seed + 25, 15, 55), color: 'hsl(38, 92%, 50%)' },
        { name: 'GBC_1', value: seededInt(seed + 26, 10, 40), color: 'hsl(142, 60%, 40%)' },
      ],
    },
  ];
}

const bairros = [
  'Jardim Santo André', 'Recreio da Borda do Campo', 'Miami Riviera',
  'Vila Metalúrgica', 'Campestre', 'Parque João Ramalho',
  'Vila Pires', 'Parque das Nações', 'Cidade São Jorge',
  'Vila Assunção', 'Jardim Irene', 'Vila Linda', 'Vila Camilópolis',
];

const servicos = ['limpeza', 'drenagem'] as const;

export function generateOccurrences(count = 200): Occurrence[] {
  const today = format(new Date(), 'dd/MM/yyyy');
  return Array.from({ length: count }, (_, i) => ({
    id: `occ-${i}`,
    lat: -23.6737 + (seededRandom(i * 3) - 0.5) * 0.08,
    lng: -46.5432 + (seededRandom(i * 3 + 1) - 0.5) * 0.08,
    intensity: seededInt(i * 3 + 2, 1, 10),
    bairro: bairros[seededInt(i * 7, 0, bairros.length - 1)],
    date: today,
    tipo: ['Alagamento', 'Inundação', 'Deslizamento'][seededInt(i * 11, 0, 2)],
    servico: servicos[seededInt(i * 13, 0, servicos.length - 1)],
    interdicao: seededRandom(i * 17) >= 0.55,
  }));
}

export function generateBairroStats(): BairroStat[] {
  return bairros.map((name, i) => ({
    name,
    count: seededInt(i + 500, 200, 3000),
  })).sort((a, b) => b.count - a.count);
}
