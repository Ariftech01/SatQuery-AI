import React, { useEffect, useRef } from 'react';
import L from 'leaflet';

export default function MapSelector({ coords, onChangeCoords }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const rectRef = useRef(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      // Default center: India [20.5937, 78.9629]
      const map = L.map(mapContainerRef.current, {
        zoomControl: false,
        attributionControl: false
      }).setView([20.5937, 78.9629], 4);

      L.control.zoom({ position: 'bottomright' }).addTo(map);

      // CartoDB Dark Matter tiles for geospatial aerospace aesthetic
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        subdomains: 'abcd',
      }).addTo(map);

      mapInstanceRef.current = map;
    }

    const map = mapInstanceRef.current;

    if (coords && coords.length === 4) {
      const [minLon, minLat, maxLon, maxLat] = coords;
      const bounds = [[minLat, minLon], [maxLat, maxLon]];

      if (rectRef.current) {
        rectRef.current.setBounds(bounds);
      } else {
        rectRef.current = L.rectangle(bounds, {
          color: '#00F0FF',
          weight: 2,
          fillColor: '#00F0FF',
          fillOpacity: 0.25,
          dashArray: '4, 4'
        }).addTo(map);
      }

      map.fitBounds(bounds, { padding: [20, 20], maxZoom: 10 });
    }
  }, [coords]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <div ref={mapContainerRef} className="map-container" />
      <div className="map-coords-bar">
        <span>BBOX [Lon, Lat]:</span>
        <span>
          {coords ? `[${coords[0].toFixed(2)}, ${coords[1].toFixed(2)}, ${coords[2].toFixed(2)}, ${coords[3].toFixed(2)}]` : 'No Region'}
        </span>
      </div>
    </div>
  );
}
