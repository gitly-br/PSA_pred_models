/**
 * Types for the real API responses from Sentry backend
 */

// GET /region/santoandre?date=YYYY-MM-DD
export interface RegionApiResponse {
  today: RegionDayData;
  tomorrow: RegionDayData;
}

export interface RegionDayData {
  all?: RegionAllData;
  tamanduatei?: RegionBasinData;
  oratorio?: RegionBasinData;
  meninos?: RegionBasinData;
  guarara?: RegionBasinData;
  [key: string]: RegionAllData | RegionBasinData | undefined;
}

export interface RegionModelEntry {
  proba: number;
  predict?: number;
  /** Pares [nome_interno, contribuição]; sinal indica direção do efeito no modelo */
  shap?: [string, number][];
}

export interface RegionAllData {
  rain_today?: {
    morning: number;
    afternoon: number;
    evening: number;
    night: number;
  };
  proba: number; // 0-1 float
  explanation?: string;
  short_explanation?: string;
  headline?: string;
  analise_completa?: string;
  models?: Record<string, RegionModelEntry>;
}

export interface RegionBasinData {
  proba: number; // 0-1 float
  explanation?: string;
  short_explanation?: string;
  headline?: string;
  analise_completa?: string;
  models?: Record<string, { proba: number }>;
}

// GET /forecast-data?date=YYYY-MM-DD
export interface ForecastHourlyItem {
  temp: number;
  rain: number;
  pop: number; // probability of precipitation 0-1
  humidity?: number;
  pressure?: number;
  wind_speed?: number;
  clouds?: number;
  dew_point?: number;
  [key: string]: number | undefined;
}

// GET /get_dates/
export interface AvailableDatesApiResponse {
  success: boolean;
  conn_problem: boolean;
  dates: string[];
  err_mg: string;
}
