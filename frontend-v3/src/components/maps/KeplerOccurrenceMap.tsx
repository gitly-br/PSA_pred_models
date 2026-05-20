import { useEffect, useMemo, useRef, useState, useDeferredValue } from 'react';
import { sampleOccurrencesForMap } from '@/lib/occurrenceMapSample';
import { Provider, useDispatch } from 'react-redux';
import KeplerGl from '@kepler.gl/components';
import { addDataToMap, replaceDataInMap } from '@kepler.gl/actions';
import { processGeojson } from '@kepler.gl/processors';
import { createStore, combineReducers, applyMiddleware, compose } from 'redux';
import keplerGlReducer, { enhanceReduxMiddleware } from '@kepler.gl/reducers';
import { getOccurrenceKeplerConfig } from '@/services/keplerConfig';
import type { Occurrence } from '@/services/mockData';

const MAP_STYLE = {
  id: 'osm-light',
  label: 'OpenStreetMap',
  url: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  icon: '',
};

function createOccurrenceStore() {
  const occReducer = keplerGlReducer.initialState({
    uiState: {
      readOnly: true,
      currentModal: null,
      activeSidePanel: null,
      mapControls: {
        visibleLayers: { show: false },
        toggle3d: { show: false },
        splitMap: { show: false },
        mapLegend: { show: true, active: true },
        mapDraw: { show: false },
        mapLocale: { show: false },
      },
    },
  });
  const occReducers = combineReducers({ keplerGl: occReducer });
  const occMiddlewares = enhanceReduxMiddleware([]);
  return createStore(occReducers, {}, compose(applyMiddleware(...occMiddlewares)));
}

interface KeplerOccurrenceMapInnerProps {
  occurrences: Occurrence[];
  mapId: string;
  height: number;
  heatmapOnly?: boolean;
}

function KeplerOccurrenceMapInner({
  occurrences,
  mapId,
  height,
  heatmapOnly = false,
}: KeplerOccurrenceMapInnerProps) {
  const dispatch = useDispatch();
  const hasInitialLoad = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const mapPoints = useMemo(
    () => sampleOccurrencesForMap(occurrences),
    [occurrences],
  );
  const deferredPoints = useDeferredValue(mapPoints);

  useEffect(() => {
    hasInitialLoad.current = false;
  }, [heatmapOnly]);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        setWidth(entry.contentRect.width);
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!deferredPoints.length && hasInitialLoad.current) {
      return;
    }

    const geojson: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: deferredPoints.map(occ => ({
        type: 'Feature' as const,
        properties: {
          id: occ.id,
          bairro: occ.bairro,
          tipo: occ.tipo,
          date: occ.date,
          intensity: occ.intensity,
          servico: occ.servico ?? '',
          interdicao: occ.interdicao ?? false,
          lat: occ.lat,
          lng: occ.lng,
        },
        geometry: {
          type: 'Point' as const,
          coordinates: [occ.lng, occ.lat],
        },
      })),
    };

    const processedData = processGeojson(geojson);
    if (!processedData) return;

    const keplerConfig = getOccurrenceKeplerConfig({ heatmapOnly });

    if (!hasInitialLoad.current) {
      dispatch(
        addDataToMap({
          datasets: {
            info: {
              label: 'Ocorrências',
              id: 'occurrences',
            },
            data: processedData,
          },
          options: {
            centerMap: deferredPoints.length > 0,
            readOnly: true,
          },
          config: keplerConfig.config as any,
        }),
      );
      hasInitialLoad.current = true;
      return;
    }

    dispatch(
      replaceDataInMap({
        datasetToReplaceId: 'occurrences',
        datasetToUse: {
          info: { id: 'occurrences', label: 'Ocorrências' },
          data: processedData,
        },
        options: {
          centerMap: deferredPoints.length > 0,
          keepExistingConfig: true,
        },
      }),
    );
  }, [deferredPoints, dispatch, heatmapOnly]);

  return (
    <div
      ref={containerRef}
      className="w-full kepler-embed bg-muted/30"
      style={{ height }}
    >
      <KeplerGl
        id={mapId}
        width={width}
        height={height}
        mapboxApiAccessToken=""
        appName="Ocorrências"
        theme="light"
        mapStylesReplaceDefault
        mapStyles={[MAP_STYLE]}
      />
    </div>
  );
}

interface KeplerOccurrenceMapProps {
  occurrences: Occurrence[];
  height?: number;
  mapId?: string;
  heatmapOnly?: boolean;
}

export default function KeplerOccurrenceMap({
  occurrences,
  height = 500,
  mapId = 'occurrence-map',
  heatmapOnly = false,
}: KeplerOccurrenceMapProps) {
  const store = useMemo(() => createOccurrenceStore(), []);

  return (
    <Provider store={store}>
      <KeplerOccurrenceMapInner
        occurrences={occurrences}
        mapId={mapId}
        height={height}
        heatmapOnly={heatmapOnly}
      />
    </Provider>
  );
}
