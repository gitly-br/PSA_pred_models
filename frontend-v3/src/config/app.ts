export const APP_CONFIG = {
  USE_MOCK_DATA: import.meta.env.VITE_USE_MOCK_DATA === 'true',
  API_BASE_URL:
    import.meta.env.VITE_API_BASE_URL ||
    (import.meta.env.DEV ? '/api' : '/api'),
  CHAMADOS_IFRAME_URL:
    import.meta.env.VITE_CHAMADOS_IFRAME_URL ||
    'https://app.powerbi.com/view?r=eyJrIjoiYzg4YmFjYWEtNzVjNi00NDNmLThkYmMtNGVlNWNlNzJkN2ZiIiwidCI6ImUwM2ZhYzdmLTdhOTktNDdhMS1hYTY5LTAzMmFjNDg4ZTcxNCJ9',
  APP_VERSION: '2.10',
  CITY_NAME: 'Santo André',
  REGION_NAME: 'all',
  DEFAULT_CENTER: [-23.6737, -46.5432] as [number, number],
  DEFAULT_ZOOM: 12,
} as const;
