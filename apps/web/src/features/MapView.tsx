import {
  AttributionControl,
  LngLatBounds,
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
  type GeoJSONSource,
} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
// MapLibre 6 ships its worker as a separate ES module; let Vite bundle it and hand us the URL.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { useEffect, useRef, useState } from 'react';
import type { LayerState } from '../components/MapControls';
import type {
  BBox,
  Epicentre,
  FeatureCollection,
  InspectionItem,
  RasterMetadata,
  ZoneFeature,
} from '../types/api';

export interface MapViewProps {
  label: string;
  bbox: BBox | null;
  raster: RasterMetadata | null;
  zones: ZoneFeature[];
  roads: FeatureCollection | null;
  places: FeatureCollection | null;
  epicentres: Epicentre[];
  items: InspectionItem[];
  selectedId: string | null;
  focusZoneId: string | null;
  onSelect: (id: string) => void;
  onZoneSelect: (zoneId: string) => void;
  layers: LayerState;
  attribution: string;
}

setWorkerUrl(workerUrl);

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] };
const MAX_MARKERS = 15;
const vis = (on: boolean) => (on ? 'visible' : 'none');

// Optional NASA GIBS basemaps (public domain). Without a connection the tiles simply do not load and the
// plain background remains: every analysis layer is served by the TriageSAR API and works offline.
const GIBS = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best';
const STYLE = {
  version: 8 as const,
  sources: {
    'gibs-satellite': {
      type: 'raster' as const,
      tiles: [
        `${GIBS}/BlueMarble_NextGeneration/default/2004-08-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg`,
      ],
      tileSize: 256,
      maxzoom: 8,
      attribution: 'Basemap: NASA Blue Marble Next Generation (2004, 500 m) via NASA GIBS',
    },
    'gibs-terrain': {
      type: 'raster' as const,
      tiles: [
        `${GIBS}/ASTER_GDEM_Greyscale_Shaded_Relief/default/2000-03-01/GoogleMapsCompatible_Level12/{z}/{y}/{x}.jpg`,
      ],
      tileSize: 256,
      maxzoom: 12,
      attribution: 'Basemap: NASA/METI ASTER GDEM shaded relief via NASA GIBS',
    },
  },
  layers: [
    { id: 'bg', type: 'background' as const, paint: { 'background-color': '#0a111e' } },
    {
      id: 'base-satellite',
      type: 'raster' as const,
      source: 'gibs-satellite',
      layout: { visibility: 'none' as const },
      paint: { 'raster-opacity': 0.85, 'raster-fade-duration': 0 },
    },
    {
      id: 'base-terrain',
      type: 'raster' as const,
      source: 'gibs-terrain',
      layout: { visibility: 'none' as const },
      paint: { 'raster-opacity': 0.55, 'raster-brightness-max': 0.75, 'raster-fade-duration': 0 },
    },
  ],
};

function el(tag: string, className: string, text?: string): HTMLElement {
  const node = document.createElement(tag);
  node.className = className;
  if (text) node.textContent = text;
  return node;
}

export default function MapView(props: MapViewProps) {
  const { bbox, raster, zones, roads, places, epicentres, items, selectedId, focusZoneId, onSelect, layers } =
    props;
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markers = useRef<Marker[]>([]);
  const rankButtons = useRef(new Map<string, HTMLButtonElement>());
  const onSelectRef = useRef(onSelect);
  const onZoneRef = useRef(props.onZoneSelect);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    onSelectRef.current = onSelect;
    onZoneRef.current = props.onZoneSelect;
  }, [onSelect, props.onZoneSelect]);

  useEffect(() => {
    if (!container.current) return;
    const map = new MapLibreMap({
      container: container.current,
      style: STYLE,
      center: [0, 0],
      zoom: 1,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      maxZoom: 15,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-left');
    map.addControl(
      new AttributionControl({
        // A collapsible attribution on phones so it does not cover the map controls.
        compact: container.current.clientWidth < 640,
        customAttribution: props.attribution,
      }),
      'bottom-right',
    );
    const markZoom = () => container.current?.classList.toggle('zoom-low', map.getZoom() < 10.4);
    map.on('zoom', markZoom);
    map.on('load', () => {
      markZoom();
      // Compact attribution starts collapsed on phones (still one tap away, as the licences require).
      container.current
        ?.querySelector('.maplibregl-ctrl-attrib')
        ?.classList.remove('maplibregl-compact-show');
      for (const id of ['roads', 'zones', 'selected', 'zone-focus', 'aoi']) {
        map.addSource(id, { type: 'geojson', data: EMPTY as never });
      }
      map.addLayer({
        id: 'roads-minor',
        type: 'line',
        source: 'roads',
        filter: [
          'in',
          ['get', 'highway'],
          ['literal', ['secondary', 'secondary_link', 'tertiary', 'tertiary_link']],
        ],
        paint: {
          'line-color': '#5f7397',
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.5, 13, 2],
        },
      });
      map.addLayer({
        id: 'roads-major',
        type: 'line',
        source: 'roads',
        filter: [
          '!',
          [
            'in',
            ['get', 'highway'],
            ['literal', ['secondary', 'secondary_link', 'tertiary', 'tertiary_link']],
          ],
        ],
        paint: {
          'line-color': '#93a7c9',
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1.1, 13, 3.5],
        },
      });
      map.addLayer({
        id: 'zones-fill',
        type: 'fill',
        source: 'zones',
        paint: { 'fill-color': '#ffffff', 'fill-opacity': 0.06 },
      });
      map.addLayer({
        id: 'zones-line',
        type: 'line',
        source: 'zones',
        paint: { 'line-color': '#ffffff', 'line-width': 2 },
      });
      map.addLayer({
        id: 'zone-focus-fill',
        type: 'fill',
        source: 'zone-focus',
        paint: { 'fill-color': '#ffd166', 'fill-opacity': 0.28 },
      });
      map.addLayer({
        id: 'zone-focus-line',
        type: 'line',
        source: 'zone-focus',
        paint: { 'line-color': '#ffd166', 'line-width': 1.5 },
      });
      map.addLayer({
        id: 'selected-casing',
        type: 'line',
        source: 'selected',
        paint: { 'line-color': '#06121f', 'line-width': 9 },
      });
      map.addLayer({
        id: 'selected-line',
        type: 'line',
        source: 'selected',
        paint: { 'line-color': '#ffd166', 'line-width': 5 },
      });
      map.addLayer({
        id: 'aoi-line',
        type: 'line',
        source: 'aoi',
        paint: { 'line-color': '#8ecbff', 'line-width': 1.5, 'line-dasharray': [3, 3] },
      });
      map.on('click', 'zones-fill', (ev) => {
        const id = ev.features?.[0]?.properties?.zone_id;
        if (typeof id === 'string') onZoneRef.current(id);
      });
      map.on('mouseenter', 'zones-fill', () => (map.getCanvas().style.cursor = 'pointer'));
      map.on('mouseleave', 'zones-fill', () => (map.getCanvas().style.cursor = ''));
      setReady(true);
    });
    mapRef.current = map;
    return () => {
      markers.current.forEach((m) => m.remove());
      markers.current = [];
      map.remove();
      mapRef.current = null;
      setReady(false);
    };
    // The map is created once; attribution text does not change during a session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Study-area outline and initial view.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !bbox) return;
    const [w, s, e, n] = bbox;
    const ring = [
      [w, s],
      [e, s],
      [e, n],
      [w, n],
      [w, s],
    ];
    (map.getSource('aoi') as GeoJSONSource).setData({
      type: 'Feature',
      properties: {},
      geometry: { type: 'LineString', coordinates: ring },
    } as never);
    // Leave room for the controls along the top and the legend in the corner.
    const wide = (container.current?.clientWidth ?? 0) > 760;
    map.setPadding({ top: 52, bottom: 0, right: wide ? 200 : 0, left: 0 });
    map.fitBounds(new LngLatBounds([w, s], [e, n]), { padding: 30, animate: false });
    container.current?.classList.toggle('zoom-low', map.getZoom() < 10.4);
  }, [ready, bbox]);

  // Raster overlays (display-only images).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const id of ['quality', 'local', 'displacement']) {
      if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(id)) map.removeSource(id);
    }
    if (!raster) return;
    map.addSource('displacement', {
      type: 'image',
      url: raster.displacement_url,
      coordinates: raster.coordinates,
    });
    map.addSource('quality', { type: 'image', url: raster.quality_url, coordinates: raster.coordinates });
    const rasterPaint = { 'raster-resampling': 'nearest' as const, 'raster-fade-duration': 0 };
    map.addLayer(
      { id: 'displacement', type: 'raster', source: 'displacement', paint: rasterPaint },
      'roads-minor',
    );
    if (raster.local_url) {
      map.addSource('local', { type: 'image', url: raster.local_url, coordinates: raster.coordinates });
      map.addLayer({ id: 'local', type: 'raster', source: 'local', paint: rasterPaint }, 'roads-minor');
    }
    map.addLayer({ id: 'quality', type: 'raster', source: 'quality', paint: rasterPaint }, 'roads-minor');
  }, [ready, raster]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource('roads') as GeoJSONSource).setData((roads ?? EMPTY) as never);
  }, [ready, roads]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource('zones') as GeoJSONSource).setData({
      type: 'FeatureCollection',
      features: zones,
    } as never);
  }, [ready, zones]);

  // Layer visibility.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const set = (id: string, on: boolean) =>
      map.getLayer(id) && map.setLayoutProperty(id, 'visibility', vis(on));
    set('base-satellite', layers.basemap === 'satellite');
    set('base-terrain', layers.basemap === 'terrain');
    set('displacement', layers.motion === 'scene');
    set('local', layers.motion === 'local');
    set('quality', layers.quality);
    set('roads-minor', layers.roads);
    set('roads-major', layers.roads);
    set('zones-fill', layers.zones);
    set('zones-line', layers.zones);
  }, [ready, layers, raster]);

  // DOM markers: place names, epicentres, zone labels and keyboard-focusable rank buttons.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    markers.current.forEach((m) => m.remove());
    markers.current = [];
    rankButtons.current.clear();
    const add = (
      node: HTMLElement,
      lonlat: [number, number],
      anchor: 'center' | 'left' | 'bottom' = 'center',
    ) => {
      markers.current.push(new Marker({ element: node, anchor }).setLngLat(lonlat).addTo(map));
    };
    for (const f of places?.features ?? []) {
      const kind = String(f.properties.place ?? '');
      const node = el('div', `mk-place ${kind}`, String(f.properties.name ?? ''));
      node.setAttribute('aria-hidden', 'true');
      add(node, f.geometry.coordinates as [number, number]);
    }
    for (const epi of epicentres) {
      const node = el('div', 'mk-epi');
      node.innerHTML =
        '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 1l2.6 6 6.4.6-4.9 4.2 1.5 6.3L10 14.8 4.4 18.1l1.5-6.3L1 7.6 7.4 7z" fill="#ffd166" stroke="#06121f" stroke-width="1"/></svg>';
      node.append(el('span', '', `USGS epicentre M ${epi.magnitude}`));
      node.setAttribute('aria-hidden', 'true');
      add(node, [epi.lon, epi.lat], 'left');
    }
    if (layers.zones) {
      for (const zone of zones) {
        const node = el('div', 'mk-zone', zone.properties.zone_id);
        node.setAttribute('aria-hidden', 'true');
        add(node, zone.properties.centroid_lonlat, 'bottom');
      }
    }
    if (layers.markers) {
      for (const item of items.slice(0, MAX_MARKERS)) {
        const button = el('button', 'mk-rank', String(item.rank)) as HTMLButtonElement;
        button.type = 'button';
        button.setAttribute(
          'aria-label',
          `Rank ${item.rank}: ${item.asset_name}. Inspection priority score ${item.score.toFixed(1)}. Open evidence.`,
        );
        button.addEventListener('click', (ev) => {
          ev.stopPropagation();
          onSelectRef.current(item.id);
        });
        rankButtons.current.set(item.id, button);
        add(button, item.marker_lonlat);
      }
    }
  }, [ready, places, epicentres, zones, items, layers.zones, layers.markers]);

  // Selection highlight.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    rankButtons.current.forEach((button, id) =>
      button.setAttribute('aria-pressed', String(id === selectedId)),
    );
    const item = items.find((i) => i.id === selectedId);
    const zone = item ? undefined : zones.find((z) => z.id === focusZoneId);
    const feature = (geometry: unknown) => ({ type: 'Feature', properties: {}, geometry }) as never;
    (map.getSource('selected') as GeoJSONSource).setData(item ? feature(item.geometry) : (EMPTY as never));
    (map.getSource('zone-focus') as GeoJSONSource).setData(zone ? feature(zone.geometry) : (EMPTY as never));
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    if (item) {
      map.easeTo({
        center: item.marker_lonlat,
        zoom: Math.max(map.getZoom(), 11),
        duration: reduce ? 0 : 600,
      });
    } else if (zone) {
      const [w, s, e, n] = zone.properties.bbox_wgs84;
      map.fitBounds(new LngLatBounds([w, s], [e, n]), {
        padding: 140,
        maxZoom: 12.5,
        duration: reduce ? 0 : 600,
      });
    }
  }, [ready, selectedId, focusZoneId, items, zones]);

  return <div ref={container} className="map" role="region" aria-label={props.label} />;
}
