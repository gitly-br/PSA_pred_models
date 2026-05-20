import { useEffect, useRef, useState } from 'react';
import { Provider, useDispatch } from 'react-redux';
import KeplerGl from '@kepler.gl/components';
import { addDataToMap } from '@kepler.gl/actions';
import { processGeojson } from '@kepler.gl/processors';
import keplerStore from '@/store/keplerStore';
import { buildBasinGeoJSON, buildMunicipalityGeoJSON, getBasinKeplerConfig } from '@/services/keplerConfig';
import type { BasinPrediction } from '@/services/mockData';

interface KeplerBasinMapInnerProps {
  basins: BasinPrediction[];
  mapId: string;
  height: number;
}

function KeplerBasinMapInner({ basins, mapId, height }: KeplerBasinMapInnerProps) {
  const dispatch = useDispatch();
  const dataLoaded = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(600);

  // Measure container width
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
    if (!basins.length || dataLoaded.current) return;

    const geojson = buildBasinGeoJSON(basins);
    const processedData = processGeojson(geojson);

    const municipalityGeojson = buildMunicipalityGeoJSON();
    const processedMunicipality = processGeojson(municipalityGeojson);

    if (processedData && processedMunicipality) {
      dispatch(
        addDataToMap({
          datasets: [
            {
              info: { label: 'Limite Municipal', id: 'municipality' },
              data: processedMunicipality,
            },
            {
              info: { label: 'Bacias Hidrográficas', id: 'basins' },
              data: processedData,
            },
          ],
          options: {
            centerMap: true,
            readOnly: true,
          },
          config: getBasinKeplerConfig().config as any,
        })
      );
      dataLoaded.current = true;
    }
  }, [basins, dispatch]);

  return (
    <div ref={containerRef} className="w-full kepler-embed" style={{ height }}>
      <KeplerGl
        id={mapId}
        width={width}
        height={height}
        mapboxApiAccessToken=""
        appName="Bacias Hidrográficas"
        theme="light"
        mapStylesReplaceDefault
        mapStyles={[
          {
            id: 'osm-light',
            label: 'OpenStreetMap',
            url: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
            icon: '',
          },
        ]}
      />
    </div>
  );
}

interface KeplerBasinMapProps {
  basins: BasinPrediction[];
  height?: number;
}

export default function KeplerBasinMap({ basins, height = 400 }: KeplerBasinMapProps) {
  return (
    <Provider store={keplerStore}>
      <KeplerBasinMapInner basins={basins} mapId="basin-map" height={height} />
    </Provider>
  );
}
