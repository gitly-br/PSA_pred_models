import type { BasinPrediction } from '@/services/mockData';

// Limite aproximado do município de Santo André - SP (área urbana principal)
// Coordenadas em formato GeoJSON [lng, lat]
export const santoAndreBoundary: GeoJSON.Feature = {
  type: 'Feature',
  properties: { id: 'santo-andre', name: 'Santo André' },
  geometry: {
    type: 'Polygon',
    coordinates: [[
      // Norte (divisa com São Paulo / Mauá)
      [-46.5800, -23.6150], [-46.5650, -23.6100], [-46.5500, -23.6080],
      [-46.5350, -23.6100], [-46.5200, -23.6150], [-46.5050, -23.6200],
      // Leste (divisa com Mauá / Ribeirão Pires)
      [-46.4950, -23.6350], [-46.4880, -23.6500], [-46.4850, -23.6650],
      [-46.4870, -23.6800], [-46.4920, -23.6950],
      // Sudeste (divisa com Rio Grande da Serra / área de mananciais)
      [-46.5000, -23.7100], [-46.5100, -23.7250], [-46.5200, -23.7350],
      // Sul (divisa com São Bernardo do Campo)
      [-46.5350, -23.7400], [-46.5500, -23.7380], [-46.5650, -23.7320],
      [-46.5800, -23.7250], [-46.5950, -23.7150],
      // Oeste (divisa com São Caetano do Sul / São Bernardo)
      [-46.6050, -23.7000], [-46.6100, -23.6850], [-46.6080, -23.6700],
      [-46.6020, -23.6550], [-46.5950, -23.6400], [-46.5880, -23.6250],
      [-46.5800, -23.6150], // fecha o polígono
    ]],
  },
};

// Polígonos aproximados das bacias hidrográficas reais de Santo André - SP
// Coordenadas em formato GeoJSON [lng, lat]
export const basinPolygons: Record<string, GeoJSON.Feature> = {
  tamanduatei: {
    type: 'Feature',
    properties: { id: 'tamanduatei', name: 'Bacia do Tamanduateí', basinIndex: 0 },
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [-46.5606, -23.6439], [-46.5217, -23.7023], [-46.4912, -23.6981],
        [-46.4859, -23.6937], [-46.4802, -23.6804], [-46.4816, -23.6481],
        [-46.4861, -23.6405], [-46.5447, -23.6109], [-46.5510, -23.6166],
        [-46.5606, -23.6439],
      ]],
    },
  },
  guarara: {
    type: 'Feature',
    properties: { id: 'guarara', name: 'Sub-bacia do Guarará', basinIndex: 1 },
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [-46.5220, -23.7146], [-46.5173, -23.7261], [-46.5150, -23.7274],
        [-46.4914, -23.7146], [-46.4892, -23.7066], [-46.4995, -23.6567],
        [-46.5107, -23.6524], [-46.5156, -23.6622], [-46.5220, -23.7146],
      ]],
    },
  },
  oratorio: {
    type: 'Feature',
    properties: { id: 'oratorio', name: 'Bacia do Oratório', basinIndex: 2 },
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [-46.5479, -23.6062], [-46.5385, -23.6303], [-46.4971, -23.6489],
        [-46.4910, -23.6489], [-46.4889, -23.6470], [-46.4830, -23.6291],
        [-46.4857, -23.6228], [-46.5479, -23.6062],
      ]],
    },
  },
  meninos: {
    type: 'Feature',
    properties: { id: 'meninos', name: 'Bacia dos Meninos', basinIndex: 3 },
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [-46.5672, -23.6501], [-46.5536, -23.6836], [-46.5291, -23.7034],
        [-46.5217, -23.7023], [-46.5227, -23.6930], [-46.5257, -23.6851],
        [-46.5454, -23.6552], [-46.5606, -23.6439], [-46.5671, -23.6498],
        [-46.5672, -23.6501],
      ]],
    },
  },
};

/**
 * Build GeoJSON for municipality boundary
 */
export function buildMunicipalityGeoJSON(): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: [santoAndreBoundary],
  };
}

/**
 * Build a GeoJSON FeatureCollection with basin predictions
 */
export function buildBasinGeoJSON(predictions: BasinPrediction[]): GeoJSON.FeatureCollection {
  const features = predictions.map(pred => {
    const polygon = basinPolygons[pred.id];
    if (!polygon) return null;
    return {
      ...polygon,
      properties: {
        ...polygon.properties,
        basinIndex: polygon.properties?.basinIndex ?? 0,
        probability: pred.probability,
        name: pred.name,
        riskLevel: pred.probability < 30 ? 'Baixo' : pred.probability < 60 ? 'Moderado' : 'Alto',
      },
    };
  }).filter(Boolean) as GeoJSON.Feature[];

  return {
    type: 'FeatureCollection',
    features,
  };
}

/**
 * Build kepler.gl config for basin visualization
 */
export function getBasinKeplerConfig() {
  return {
    version: 'v1',
    config: {
      visState: {
        filters: [],
        layers: [
          // Municipality boundary layer
          {
            id: 'municipality',
            type: 'geojson',
            config: {
              dataId: 'municipality',
              label: 'Limite Municipal',
              color: [80, 80, 80],
              columns: { geojson: '_geojson' },
              isVisible: true,
              visConfig: {
                opacity: 0.05,
                strokeOpacity: 1,
                thickness: 3,
                strokeColor: [60, 60, 60],
                filled: true,
                stroked: true,
                enable3d: false,
                wireframe: false,
              },
              textLabel: [],
            },
            visualChannels: {
              colorField: null,
              colorScale: 'quantile',
              sizeField: null,
              sizeScale: 'linear',
              strokeColorField: null,
              strokeColorScale: 'quantile',
            },
          },
          // Basin polygons layer
          {
            id: 'basins',
            type: 'geojson',
            config: {
              dataId: 'basins',
              label: 'Bacias Hidrográficas',
              color: [100, 100, 230],
              columns: { geojson: '_geojson' },
              isVisible: true,
              visConfig: {
                opacity: 0.45,
                strokeOpacity: 0.8,
                thickness: 1.5,
                strokeColor: [40, 40, 80],
                colorRange: {
                  name: 'Bacias',
                  type: 'qualitative',
                  category: 'Custom',
                  colors: [
                    '#3498db', // azul - Tamanduateí
                    '#2ecc71', // verde - Guarará
                    '#e67e22', // laranja - Oratório
                    '#9b59b6', // roxo - Meninos
                  ],
                },
                filled: true,
                stroked: true,
                enable3d: false,
                wireframe: false,
              },
              textLabel: [
                {
                  field: { name: 'name', type: 'string' },
                  color: [0, 0, 0],
                  size: 14,
                  offset: [0, 0],
                  anchor: 'middle',
                  alignment: 'center',
                },
              ],
            },
            visualChannels: {
              colorField: { name: 'basinIndex', type: 'integer' },
              colorScale: 'ordinal',
              sizeField: null,
              sizeScale: 'linear',
              heightField: null,
              heightScale: 'linear',
              strokeColorField: null,
              strokeColorScale: 'quantile',
            },
          },
        ],
        interactionConfig: {
          tooltip: {
            fieldsToShow: {
              basins: [
                { name: 'name', format: null },
                { name: 'probability', format: null },
                { name: 'riskLevel', format: null },
              ],
              municipality: [
                { name: 'name', format: null },
              ],
            },
            compareMode: false,
            compareType: 'absolute',
            enabled: true,
          },
          brush: { size: 0.5, enabled: false },
          geocoder: { enabled: false },
          coordinate: { enabled: false },
        },
      },
      mapState: {
        bearing: 0,
        dragRotate: false,
        latitude: -23.673,
        longitude: -46.543,
        pitch: 0,
        zoom: 12,
        isSplit: false,
      },
      mapStyle: {
        styleType: 'osm-light',
      },
    },
  };
}

export type OccurrenceKeplerOptions = {
  dark?: boolean;
  /** Apenas mancha de calor (comparação lado a lado). */
  heatmapOnly?: boolean;
};

/**
 * Build kepler.gl config for occurrences visualization
 */
export function getOccurrenceKeplerConfig(opts: OccurrenceKeplerOptions = {}) {
  const dark = opts.dark ?? false;
  const heatmapOnly = opts.heatmapOnly ?? false;

  const heatColors = dark
    ? ['#4DD0E1', '#81C784', '#FFEE58', '#FFB74D', '#FF7043', '#E040FB']
    : ['#FFC300', '#F1920E', '#E3611C', '#C70039', '#900C3F', '#5A1846'];

  const pointColors = dark
    ? ['#80DEEA', '#FFD54F', '#FF8A65', '#F48FB1']
    : ['#FFC300', '#E3611C', '#C70039', '#900C3F'];

  const layers: object[] = [
    {
      id: 'occurrences-heat',
      type: 'heatmap',
      config: {
        dataId: 'occurrences',
        label: 'Manchas de ocorrências',
        columns: { lat: 'lat', lng: 'lng' },
        isVisible: true,
        visConfig: {
          opacity: heatmapOnly ? 0.88 : 0.7,
          colorRange: {
            name: dark ? 'Heat Dark' : 'Global Warming',
            type: 'sequential',
            category: 'Custom',
            colors: heatColors,
          },
          radius: heatmapOnly ? 28 : 20,
        },
      },
      visualChannels: {
        weightField: { name: 'intensity', type: 'integer' },
        weightScale: 'linear',
      },
    },
  ];

  if (!heatmapOnly) {
    layers.push({
      id: 'occurrences-points',
      type: 'point',
      config: {
        dataId: 'occurrences',
        label: 'Ocorrências',
        columns: { lat: 'lat', lng: 'lng' },
        isVisible: !dark,
        visConfig: {
          radius: 8,
          fixedRadius: false,
          opacity: dark ? 0.85 : 0.6,
          outline: dark,
          outlineColor: dark ? [255, 255, 255] : undefined,
          filled: true,
          colorRange: {
            name: 'Risk',
            type: 'sequential',
            category: 'Custom',
            colors: pointColors,
          },
        },
        textLabel: [],
      },
      visualChannels: {
        colorField: { name: 'intensity', type: 'integer' },
        colorScale: 'quantize',
        sizeField: { name: 'intensity', type: 'integer' },
        sizeScale: 'sqrt',
      },
    });
  }

  return {
    version: 'v1',
    config: {
      visState: {
        filters: [],
        layers,
        interactionConfig: {
          tooltip: {
            fieldsToShow: {
              occurrences: [
                { name: 'bairro', format: null },
                { name: 'tipo', format: null },
                { name: 'date', format: null },
                { name: 'intensity', format: null },
              ],
            },
            enabled: true,
          },
          brush: { enabled: false },
          geocoder: { enabled: false },
          coordinate: { enabled: false },
        },
      },
      mapState: {
        bearing: 0,
        dragRotate: false,
        latitude: -23.673,
        longitude: -46.543,
        pitch: 0,
        zoom: 11,
        isSplit: false,
      },
      mapStyle: {
        styleType: dark ? 'osm-dark' : 'osm-light',
      },
    },
  };
}
