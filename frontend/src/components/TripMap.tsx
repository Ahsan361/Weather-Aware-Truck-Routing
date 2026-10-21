import { Map as MapLibreMap, Marker, NavigationControl, Popup, setWorkerUrl } from 'maplibre-gl'
import type { FilterSpecification, GeoJSONSource } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import type { FeatureCollection } from 'geojson'
import { memo, useEffect, useRef, useState } from 'react'
import type { AnalyzeResponse } from '../api/types'
import { checkpointPoints, heatmapPoints, heatWeight, levelColor, routeBounds, routeLines } from '../lib/mapData'
import { buildCheckpointPopup } from './checkpointPopup'
import styles from './TripMap.module.css'

// Vite's dev server pre-bundles maplibre-gl and leaves its worker file behind, so point at it
// explicitly. The worker is a single self-contained file, which also keeps production builds safe.
setWorkerUrl(workerUrl)

// free vector tiles, no key needed
const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'
const US_CENTER: [number, number] = [-98.5, 39.5]
const OTHER_ROUTE_COLOR = '#8793a1'

const HEAT = 'heat'
const ROUTES = 'routes'
const CHECKPOINTS = 'checkpoints'

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

interface Props {
  result: AnalyzeResponse | null
  selectedRouteId: number | null
  focusedCheckpoint: number | null
  heatmapVisible: boolean
  heatmapHour: number
  onSelectRoute: (routeId: number) => void
  onFocusCheckpoint: (index: number | null) => void
}

function isRoute(id: number | null) {
  return ['==', ['get', 'routeId'], id ?? -1] as FilterSpecification
}

function addLayers(map: MapLibreMap) {
  // slot everything under the basemap's labels so place names stay readable
  const labelLayer = map.getStyle().layers.find((layer) => layer.type === 'symbol')?.id

  map.addSource(HEAT, { type: 'geojson', data: EMPTY })
  map.addSource(ROUTES, { type: 'geojson', data: EMPTY })
  map.addSource(CHECKPOINTS, { type: 'geojson', data: EMPTY })

  map.addLayer(
    {
      id: 'heat',
      type: 'heatmap',
      source: HEAT,
      paint: {
        'heatmap-weight': heatWeight(0, 48),
        'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 3, 1.1, 9, 1.8],
        'heatmap-radius': ['interpolate', ['exponential', 2], ['zoom'], 3, 22, 5, 46, 7, 90, 9, 160, 12, 260],
        'heatmap-opacity': 0.88,
        'heatmap-color': [
          'interpolate',
          ['linear'],
          ['heatmap-density'],
          0,
          'rgba(242,194,0,0)',
          0.12,
          'rgba(242,194,0,0.5)',
          0.35,
          'rgba(240,140,0,0.72)',
          0.65,
          'rgba(224,49,49,0.85)',
          1,
          'rgba(106,27,154,0.95)',
        ],
      },
      layout: { visibility: 'none' },
    },
    labelLayer,
  )

  // white outline under every route so lines stay readable on busy basemap areas
  map.addLayer(
    {
      id: 'routes-casing',
      type: 'line',
      source: ROUTES,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#ffffff', 'line-width': 7, 'line-opacity': 0.9 },
    },
    labelLayer,
  )
  // a wide invisible copy of the unselected routes, so they are easy to click
  map.addLayer(
    {
      id: 'routes-hit',
      type: 'line',
      source: ROUTES,
      filter: ['!=', ['get', 'routeId'], -1],
      paint: { 'line-color': '#000000', 'line-width': 18, 'line-opacity': 0 },
    },
    labelLayer,
  )
  map.addLayer(
    {
      id: 'routes-other',
      type: 'line',
      source: ROUTES,
      filter: ['!=', ['get', 'routeId'], -1],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': OTHER_ROUTE_COLOR, 'line-width': 4, 'line-opacity': 0.85 },
    },
    labelLayer,
  )
  map.addLayer(
    {
      id: 'routes-selected',
      type: 'line',
      source: ROUTES,
      filter: isRoute(null),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': levelColor(), 'line-width': 6 },
    },
    labelLayer,
  )

  map.addLayer(
    {
      id: 'checkpoints-halo',
      type: 'circle',
      source: CHECKPOINTS,
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 4, 8, 7, 12, 10],
        'circle-color': '#ffffff',
      },
    },
    labelLayer,
  )
  map.addLayer(
    {
      id: 'checkpoints',
      type: 'circle',
      source: CHECKPOINTS,
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 2.5, 8, 5, 12, 8],
        'circle-color': levelColor(),
      },
    },
    labelLayer,
  )
  map.addLayer(
    {
      id: 'checkpoint-focus',
      type: 'circle',
      source: CHECKPOINTS,
      filter: ['==', ['get', 'index'], -1],
      paint: {
        'circle-radius': 13,
        'circle-color': 'rgba(0,0,0,0)',
        'circle-stroke-width': 3,
        'circle-stroke-color': '#17202a',
      },
    },
    labelLayer,
  )
}

function pointerOnHover(map: MapLibreMap, layerId: string) {
  map.on('mouseenter', layerId, () => (map.getCanvas().style.cursor = 'pointer'))
  map.on('mouseleave', layerId, () => (map.getCanvas().style.cursor = ''))
}

function pin(label: string, className: string): HTMLElement {
  const node = document.createElement('div')
  node.className = `${styles.pin} ${className}`
  node.textContent = label
  return node
}

function TripMapView({
  result,
  selectedRouteId,
  focusedCheckpoint,
  heatmapVisible,
  heatmapHour,
  onSelectRoute,
  onFocusCheckpoint,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const markersRef = useRef<Marker[]>([])
  const popupRef = useRef<{ popup: Popup; onClose: () => void } | null>(null)
  const [ready, setReady] = useState(false)

  // map event handlers are registered once, so they read the latest callbacks from here
  const callbacks = useRef({ onSelectRoute, onFocusCheckpoint })
  useEffect(() => {
    callbacks.current = { onSelectRoute, onFocusCheckpoint }
  })

  const selectedRoute = result?.routes.find((route) => route.id === selectedRouteId)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const map = new MapLibreMap({
      container,
      style: STYLE_URL,
      center: US_CENTER,
      zoom: 3.4,
      attributionControl: { compact: true },
      pitchWithRotate: false,
      dragRotate: false,
    })
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    map.touchZoomRotate.disableRotation()

    map.on('load', () => {
      addLayers(map)

      map.on('click', 'routes-hit', (event) => {
        const id = event.features?.[0]?.properties?.routeId
        if (typeof id === 'number') callbacks.current.onSelectRoute(id)
      })
      map.on('click', 'checkpoints', (event) => {
        const index = event.features?.[0]?.properties?.index
        if (typeof index === 'number') callbacks.current.onFocusCheckpoint(index)
      })
      pointerOnHover(map, 'routes-hit')
      pointerOnHover(map, 'checkpoints')

      setReady(true)
    })

    const resizeObserver = new ResizeObserver(() => map.resize())
    resizeObserver.observe(container)
    mapRef.current = map

    return () => {
      resizeObserver.disconnect()
      map.remove()
      mapRef.current = null
      markersRef.current = []
      popupRef.current = null
      setReady(false)
    }
  }, [])

  // new result: load the geometry and heat data, frame the routes, drop the A and B pins
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

    ;(map.getSource(ROUTES) as GeoJSONSource).setData(result ? routeLines(result.routes) : EMPTY)
    ;(map.getSource(HEAT) as GeoJSONSource).setData(result ? heatmapPoints(result.heatmap) : EMPTY)

    markersRef.current.forEach((marker) => marker.remove())
    markersRef.current = []
    if (!result) return

    const first = result.routes[0]?.checkpoints
    if (first?.length) {
      const start = first[0]
      const end = first[first.length - 1]
      markersRef.current = [
        new Marker({ element: pin('A', styles.start) }).setLngLat([start.lon, start.lat]).addTo(map),
        new Marker({ element: pin('B', styles.end) }).setLngLat([end.lon, end.lat]).addTo(map),
      ]
    }

    const bounds = routeBounds(result.routes)
    if (bounds) {
      map.fitBounds(bounds, {
        padding: { top: 70, bottom: 130, left: 60, right: 60 },
        maxZoom: 9,
        duration: 1000,
      })
    }
  }, [ready, result])

  // selection decides which route is drawn in colour and which checkpoints are shown
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

    map.setFilter('routes-selected', isRoute(selectedRouteId))
    map.setFilter('routes-other', ['!=', ['get', 'routeId'], selectedRouteId ?? -1])
    map.setFilter('routes-hit', ['!=', ['get', 'routeId'], selectedRouteId ?? -1])
    map.setPaintProperty('routes-casing', 'line-width', [
      'case',
      ['==', ['get', 'routeId'], selectedRouteId ?? -1],
      9,
      6,
    ])
    ;(map.getSource(CHECKPOINTS) as GeoJSONSource).setData(checkpointPoints(selectedRoute))
  }, [ready, selectedRouteId, selectedRoute])

  // the checkpoint popup and its highlight ring
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

    if (popupRef.current) {
      // detach first, or removing the old popup would report "closed" and clear the new focus
      popupRef.current.popup.off('close', popupRef.current.onClose)
      popupRef.current.popup.remove()
      popupRef.current = null
    }
    map.setFilter('checkpoint-focus', ['==', ['get', 'index'], focusedCheckpoint ?? -1])

    const checkpoint = focusedCheckpoint === null ? undefined : selectedRoute?.checkpoints[focusedCheckpoint]
    if (!checkpoint || !result) return

    const onClose = () => callbacks.current.onFocusCheckpoint(null)
    const popup = new Popup({ offset: 16, maxWidth: '320px', closeOnClick: false })
      .setLngLat([checkpoint.lon, checkpoint.lat])
      .setDOMContent(buildCheckpointPopup(checkpoint, result.origin.timezone))
      .addTo(map)
    popup.on('close', onClose)
    popupRef.current = { popup, onClose }

    if (!map.getBounds().contains([checkpoint.lon, checkpoint.lat])) {
      map.easeTo({ center: [checkpoint.lon, checkpoint.lat], duration: 600 })
    }
  }, [ready, result, selectedRoute, focusedCheckpoint])

  // heatmap on/off
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    map.setLayoutProperty('heat', 'visibility', heatmapVisible ? 'visible' : 'none')
  }, [ready, heatmapVisible])

  // dragging the time slider only swaps this expression, no data is touched
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !heatmapVisible) return
    map.setPaintProperty('heat', 'heatmap-weight', heatWeight(heatmapHour, result?.heatmap.hours ?? 48))
  }, [ready, result, heatmapVisible, heatmapHour])

  return <div ref={containerRef} className={styles.map} data-testid="trip-map" />
}

export const TripMap = memo(TripMapView)
