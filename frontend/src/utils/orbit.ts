export type OrbitalElements = {
  epoch_time: string;
  inclination: number;
  eccentricity: number;
  mean_motion: number;
  raan: number;
  arg_of_perigee: number;
  mean_anomaly: number;
};

const MU = 398600.4418; // km^3/s^2
const EARTH_RADIUS = 6378.137; // km, equatorial
const DEG = Math.PI / 180;

export function elementEpoch(value: string): number {
  return Date.parse(value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
}

export function propagateElements(elements: OrbitalElements, atMs: number) {
  const epoch = elementEpoch(elements.epoch_time);
  const { eccentricity: e, mean_motion: revDay } = elements;
  if (!Number.isFinite(epoch) || !Number.isFinite(atMs) ||
      !Number.isFinite(e) || e < 0 || e >= 1 ||
      !Number.isFinite(revDay) || revDay <= 0 ||
      ![elements.inclination, elements.raan, elements.arg_of_perigee, elements.mean_anomaly].every(Number.isFinite)) {
    return null;
  }
  const n = revDay * 2 * Math.PI / 86400;
  const a = Math.cbrt(MU / (n * n));
  const mean = (elements.mean_anomaly * DEG + n * ((atMs - epoch) / 1000)) % (2 * Math.PI);
  let eccentric = mean;
  for (let j = 0; j < 12; j++) {
    eccentric -= (eccentric - e * Math.sin(eccentric) - mean) / (1 - e * Math.cos(eccentric));
  }
  const anomaly = Math.atan2(Math.sqrt(1 - e * e) * Math.sin(eccentric), Math.cos(eccentric) - e);
  const radius = a * (1 - e * Math.cos(eccentric));
  const inclination = elements.inclination * DEG;
  const raan = elements.raan * DEG;
  const argument = elements.arg_of_perigee * DEG + anomaly;
  const x = radius * (Math.cos(raan) * Math.cos(argument) - Math.sin(raan) * Math.sin(argument) * Math.cos(inclination));
  const y = radius * (Math.sin(raan) * Math.cos(argument) + Math.cos(raan) * Math.sin(argument) * Math.cos(inclination));
  const z = radius * Math.sin(argument) * Math.sin(inclination);
  const julianDate = atMs / 86400000 + 2440587.5;
  const gmst = ((280.46061837 + 360.98564736629 * (julianDate - 2451545)) % 360) * DEG;
  const longitude = Math.atan2(y, x) - gmst;
  const lng = ((longitude / DEG + 540) % 360) - 180;
  const lat = Math.atan2(z, Math.hypot(x, y)) / DEG;
  const altitudeKm = radius - EARTH_RADIUS;
  const velocityKmS = Math.sqrt(MU * (2 / radius - 1 / a));
  return { lat, lng, altitudeKm, velocityKmS, periodMs: 86400000 / revDay };
}

export function orbitGroundTrack(elements: OrbitalElements, atMs: number) {
  const periodMs = 86400000 / elements.mean_motion;
  if (!Number.isFinite(periodMs) || periodMs <= 0) return [];
  return Array.from({ length: 91 }, (_, index) =>
    propagateElements(elements, atMs + (index / 90 - 0.5) * periodMs),
  ).filter((point): point is NonNullable<typeof point> => point !== null)
    .map(({ lat, lng }) => ({ lat, lng }));
}
