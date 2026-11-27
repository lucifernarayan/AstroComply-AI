"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

export type FleetPosition = {
  asset_id: number;
  display_name: string;
  norad_id?: number | null;
  status: "propagated" | "stale" | "unavailable" | "failed";
  reason?: string;
  latitude_deg?: number;
  longitude_deg?: number;
  altitude_km?: number;
  epoch?: string;
  at: string;
  source?: string;
  filename?: string;
  sha256?: string;
  uploaded_at?: string;
  method?: string;
  frame?: string;
  geodetic_frame?: string;
  quality?: string;
};

const Globe = dynamic(() => import("react-globe.gl"), { ssr: false });

export function FleetGlobe({ positions, selectedId, onSelect }: {
  positions: FleetPosition[];
  selectedId: number | null;
  onSelect: (assetId: number) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 640, height: 420 });
  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setSize({ width: Math.max(300, entry.contentRect.width), height: 420 });
    });
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const plotted = positions.filter((item) => item.status === "propagated" &&
    item.latitude_deg != null && item.longitude_deg != null && item.altitude_km != null);
  return <div ref={container} className="relative h-[420px] w-full border border-cyan-900 bg-[#050a11]">
    <Globe
      width={size.width} height={size.height}
      backgroundColor="#050a11"
      globeImageUrl="//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
      showAtmosphere atmosphereColor="#4dd9f5"
      pointsData={plotted}
      pointLat="latitude_deg" pointLng="longitude_deg"
      pointAltitude={(value: object) => Math.min(0.6, Math.max(0.02,
        ((value as FleetPosition).altitude_km ?? 0) / 6378.137))}
      pointRadius={(value: object) => (value as FleetPosition).asset_id === selectedId ? 0.6 : 0.35}
      pointColor={(value: object) => (value as FleetPosition).asset_id === selectedId ? "#ffffff" : "#4dd9f5"}
      onPointClick={(value: object) => onSelect((value as FleetPosition).asset_id)}
      pointLabel={(value: object) => {
        const point = value as FleetPosition;
        return `${point.display_name} · ${point.source ?? "unknown source"} · epoch ${point.epoch ?? "unknown"}`;
      }}
    />
    {plotted.length === 0 && <p className="pointer-events-none absolute bottom-3 left-3 bg-[#07111c]/90 p-2 text-xs text-slate-300">No current uploaded TLEs to plot.</p>}
    <p className="pointer-events-none absolute left-3 top-3 bg-[#07111c]/90 p-2 text-xs text-cyan-200">SGP4 propagated positions · WGS84 map · predictions, not observations</p>
  </div>;
}
