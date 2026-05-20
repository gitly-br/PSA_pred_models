import { useEffect, useRef, useState } from 'react';
import { useTheme } from 'next-themes';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { APP_CONFIG } from '@/config/app';
import { featureCollectionBounds, mergeMapBounds } from '@/lib/geojsonBounds';
import {
  basinFillColorByModel,
  floodColorByPercent,
  predictionsByModelId,
} from '@/lib/basinMapStyles';
import type { BasinPrediction } from '@/services/mockData';

import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

// @ts-expect-error Leaflet icon URL shim
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

interface BasinMapProps {
  className?: string;
  basins?: BasinPrediction[];
  visibleBasinIds?: string[];
}

function mapStrokeFromCss(): string {
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--map-stroke').trim();
  return raw ? `hsl(${raw})` : 'hsl(220 32% 18%)';
}

export default function BasinMap({ className, basins = [], visibleBasinIds = [] }: BasinMapProps) {
  const { resolvedTheme } = useTheme();
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const basinLayerRef = useRef<L.GeoJSON | null>(null);
  const floodLayerRef = useRef<L.GeoJSON | null>(null);
  const [geoData, setGeoData] = useState<{
    sub: GeoJSON.FeatureCollection;
    flood: GeoJSON.FeatureCollection;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const base = import.meta.env.BASE_URL;

    (async () => {
      try {
        const [sub, flood] = await Promise.all([
          fetch(`${base}geojson/sub-bacias.geojson`).then(r => {
            if (!r.ok) throw new Error(`sub-bacias: ${r.status}`);
            return r.json() as Promise<GeoJSON.FeatureCollection>;
          }),
          fetch(`${base}geojson/Areas_alagaveis.geojson`).then(r => {
            if (!r.ok) throw new Error(`Areas_alagaveis: ${r.status}`);
            return r.json() as Promise<GeoJSON.FeatureCollection>;
          }),
        ]);
        if (!cancelled) setGeoData({ sub, flood });
      } catch (e) {
        console.error('[BasinMap] Erro ao carregar GeoJSON:', e);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!geoData || !mapRef.current) return;

    const visibleSet = new Set(
      (visibleBasinIds.length ? visibleBasinIds : basins.map(b => b.id)).map(id => id.toLowerCase()),
    );
    const predMap = predictionsByModelId(basins);

    const isVisibleFeature = (feature: GeoJSON.Feature) => {
      const modelId = String((feature.properties as Record<string, unknown>)?.MODELO ?? '').toLowerCase();
      return visibleSet.size === 0 ? true : visibleSet.has(modelId);
    };

    const filterCollection = (fc: GeoJSON.FeatureCollection): GeoJSON.FeatureCollection => ({
      ...fc,
      features: fc.features.filter(f => isVisibleFeature(f as GeoJSON.Feature)),
    });

    const filteredSub = filterCollection(geoData.sub);
    const filteredFlood = filterCollection(geoData.flood);

    const floodStyle = (feature: GeoJSON.Feature): L.PathOptions => {
      const modelo = String((feature.properties as Record<string, unknown>)?.MODELO ?? '');
      const pct = predMap[modelo];
      const stroke = floodColorByPercent(pct);
      const w = 1 + (pct != null ? (pct / 100) * 2.25 : 0);
      return {
        fillColor: stroke,
        fillOpacity: 0.62,
        color: stroke,
        weight: w,
        lineJoin: 'round',
        lineCap: 'round',
      };
    };

    const basinOutline = mapStrokeFromCss();

    if (!mapInstance.current) {
      const map = L.map(mapRef.current, {
        center: [...APP_CONFIG.DEFAULT_CENTER] as L.LatLngExpression,
        zoom: APP_CONFIG.DEFAULT_ZOOM,
        zoomControl: true,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);

      basinLayerRef.current = L.geoJSON(filteredSub, {
        style: feature => ({
          fillColor: basinFillColorByModel(
            (feature.properties as Record<string, unknown>)?.MODELO as string | undefined,
          ),
          fillOpacity: 0.38,
          color: basinOutline,
          weight: 1.25,
          lineJoin: 'round',
          lineCap: 'round',
        }),
        onEachFeature: (feature, layer) => {
          const p = feature.properties as Record<string, unknown>;
          layer.bindPopup(
            `<strong>${String(p?.NOM_SUB_BA ?? '')}</strong><br/>${String(p?.NOM_BACIA ?? '')}`,
          );
        },
      }).addTo(map);

      floodLayerRef.current = L.geoJSON(filteredFlood, {
        style: feature => floodStyle(feature),
        onEachFeature: (feature, layer) => {
          const p = feature.properties as Record<string, unknown>;
          layer.bindPopup(`<span>fid: ${String(p?.fid ?? '')}</span>`);
        },
      }).addTo(map);

      const bounds = mergeMapBounds(featureCollectionBounds(filteredSub), featureCollectionBounds(filteredFlood));
      if (bounds) {
        map.fitBounds(bounds, { padding: [20, 20], maxZoom: 16 });
      }

      mapInstance.current = map;
    } else {
      basinLayerRef.current?.remove();
      floodLayerRef.current?.remove();

      basinLayerRef.current = L.geoJSON(filteredSub, {
        style: feature => ({
          fillColor: basinFillColorByModel(
            (feature.properties as Record<string, unknown>)?.MODELO as string | undefined,
          ),
          fillOpacity: 0.38,
          color: basinOutline,
          weight: 1.25,
          lineJoin: 'round',
          lineCap: 'round',
        }),
        onEachFeature: (feature, layer) => {
          const p = feature.properties as Record<string, unknown>;
          layer.bindPopup(
            `<strong>${String(p?.NOM_SUB_BA ?? '')}</strong><br/>${String(p?.NOM_BACIA ?? '')}`,
          );
        },
      }).addTo(mapInstance.current);

      floodLayerRef.current = L.geoJSON(filteredFlood, {
        style: feature => floodStyle(feature),
        onEachFeature: (feature, layer) => {
          const p = feature.properties as Record<string, unknown>;
          layer.bindPopup(`<span>fid: ${String(p?.fid ?? '')}</span>`);
        },
      }).addTo(mapInstance.current);
    }
  }, [geoData, basins, visibleBasinIds]);

  useEffect(() => {
    const layer = basinLayerRef.current;
    if (!layer) return;
    const stroke = mapStrokeFromCss();
    layer.eachLayer(ly => {
      if (ly instanceof L.Path) {
        ly.setStyle({ color: stroke });
      }
    });
  }, [resolvedTheme]);

  useEffect(
    () => () => {
      mapInstance.current?.remove();
      mapInstance.current = null;
      basinLayerRef.current = null;
      floodLayerRef.current = null;
    },
    [],
  );

  return (
    <div ref={mapRef} className={className} style={{ minHeight: '350px' }} />
  );
}
