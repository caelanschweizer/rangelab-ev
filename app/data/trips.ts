export type TelemetryPoint = {
  elapsedMinutes: number;
  distanceKm: number;
  speedKph: number;
  powerKw: number;
  socPct: number;
  batteryTempC: number;
  cumulativeEnergyKwh: number;
};

export type TripDataQuality = {
  coveragePct: number;
  displayedSamples: number;
  expectedSamples: number;
  unexpectedGapCount: number;
  outOfRangeValuesIgnored: number;
};

export type TelemetryTrip = {
  id: string;
  shortLabel: string;
  routeLabel: string;
  dateLabel: string;
  description: string;
  condition: string;
  ambientC: number;
  distanceKm: number;
  durationMinutes: number;
  startSoc: number;
  endSoc: number;
  energyUsedKwh: number;
  regenKwh: number;
  efficiencyKwhPer100Km: number;
  averageSpeedKph: number;
  quality: TripDataQuality;
  points: TelemetryPoint[];
};

type TripSeed = Omit<TelemetryTrip, "points"> & {
  thermalRiseC: number;
  powerScale: number;
  phase: number;
};

const round = (value: number, precision = 1) => {
  const multiplier = 10 ** precision;
  return Math.round(value * multiplier) / multiplier;
};

function buildTelemetry(seed: TripSeed): TelemetryPoint[] {
  const sampleCount = 33;

  return Array.from({ length: sampleCount }, (_, index) => {
    const progress = index / (sampleCount - 1);
    const stopPulse = index > 0 && index < sampleCount - 1 && index % 8 === 0;
    const regenPulse = index > 2 && (index % 9 === 0 || index % 13 === 0);
    const speedWave =
      seed.averageSpeedKph +
      Math.sin(index * 0.82 + seed.phase) * 13 +
      Math.cos(index * 0.31 + seed.phase) * 7;
    const speedKph =
      index === 0 || index === sampleCount - 1 || stopPulse
        ? 0
        : Math.max(12, Math.min(105, speedWave));
    const drivePower =
      seed.powerScale +
      Math.sin(index * 0.74 + seed.phase) * seed.powerScale * 0.48 +
      Math.max(0, speedKph - seed.averageSpeedKph) * 0.18;
    const powerKw = regenPulse
      ? -(7.5 + ((index * 17) % 10))
      : stopPulse
        ? 1.4
        : Math.max(2.5, drivePower);
    const progressNoise = Math.sin(progress * Math.PI) * 0.18;
    const socPct =
      seed.startSoc - (seed.startSoc - seed.endSoc) * progress - progressNoise;
    const batteryTempC =
      seed.ambientC +
      8.5 +
      seed.thermalRiseC * progress +
      Math.sin(progress * Math.PI * 2) * 0.35;
    const cumulativeEnergyKwh =
      seed.energyUsedKwh * progress + Math.sin(progress * Math.PI) * 0.07;

    return {
      elapsedMinutes: round(seed.durationMinutes * progress, 0),
      distanceKm: round(seed.distanceKm * progress, 1),
      speedKph: round(speedKph, 0),
      powerKw: round(powerKw, 1),
      socPct: round(socPct, 1),
      batteryTempC: round(batteryTempC, 1),
      cumulativeEnergyKwh: round(cumulativeEnergyKwh, 2),
    };
  });
}

function createTrip(seed: TripSeed): TelemetryTrip {
  const generationFields = new Set(["thermalRiseC", "powerScale", "phase"]);
  const trip = Object.fromEntries(
    Object.entries(seed).filter(([key]) => !generationFields.has(key)),
  ) as Omit<TripSeed, "thermalRiseC" | "powerScale" | "phase">;
  return { ...trip, points: buildTelemetry(seed) };
}

export const SAMPLE_TRIPS: TelemetryTrip[] = [
  createTrip({
    id: "cold-commute",
    shortLabel: "Cold commute",
    routeLabel: "Synthetic mixed-road loop",
    dateLabel: "UI trip 01 · winter morning",
    description: "Mixed arterial traffic with a preconditioned cabin and two regenerative descents.",
    condition: "Cold · mixed roads",
    ambientC: -4,
    distanceKm: 32.4,
    durationMinutes: 38,
    startSoc: 71,
    endSoc: 62,
    energyUsedKwh: 5.45,
    regenKwh: 1.21,
    efficiencyKwhPer100Km: 16.8,
    averageSpeedKph: 51.2,
    quality: {
      coveragePct: 100,
      displayedSamples: 33,
      expectedSamples: 33,
      unexpectedGapCount: 0,
      outOfRangeValuesIgnored: 0,
    },
    thermalRiseC: 5.2,
    powerScale: 18,
    phase: 0.4,
  }),
  createTrip({
    id: "lakeside-loop",
    shortLabel: "Lakeside loop",
    routeLabel: "Synthetic mild-weather loop",
    dateLabel: "UI trip 02 · spring afternoon",
    description: "Steady suburban running with mild weather and a short highway section.",
    condition: "Mild · flowing traffic",
    ambientC: 18,
    distanceKm: 51.8,
    durationMinutes: 52,
    startSoc: 82,
    endSoc: 69,
    energyUsedKwh: 7.36,
    regenKwh: 1.48,
    efficiencyKwhPer100Km: 14.2,
    averageSpeedKph: 59.8,
    quality: {
      coveragePct: 100,
      displayedSamples: 33,
      expectedSamples: 33,
      unexpectedGapCount: 0,
      outOfRangeValuesIgnored: 0,
    },
    thermalRiseC: 3.8,
    powerScale: 16,
    phase: 1.3,
  }),
  createTrip({
    id: "winter-errands",
    shortLabel: "Winter errands",
    routeLabel: "Synthetic multi-stop circuit",
    dateLabel: "UI trip 03 · winter evening",
    description: "Four short stops, a cold-soaked battery, and sustained cabin heating.",
    condition: "Very cold · stop-and-go",
    ambientC: -12,
    distanceKm: 18.7,
    durationMinutes: 27,
    startSoc: 58,
    endSoc: 51,
    energyUsedKwh: 4.31,
    regenKwh: 0.74,
    efficiencyKwhPer100Km: 23.0,
    averageSpeedKph: 41.6,
    quality: {
      coveragePct: 100,
      displayedSamples: 33,
      expectedSamples: 33,
      unexpectedGapCount: 0,
      outOfRangeValuesIgnored: 0,
    },
    thermalRiseC: 7.1,
    powerScale: 20,
    phase: 2.1,
  }),
  createTrip({
    id: "summer-highway",
    shortLabel: "Summer highway",
    routeLabel: "Synthetic expressway segment",
    dateLabel: "UI trip 04 · summer daytime",
    description: "Warm-weather highway segment with stable speed and light climate control.",
    condition: "Warm · highway",
    ambientC: 28,
    distanceKm: 74.2,
    durationMinutes: 49,
    startSoc: 90,
    endSoc: 69,
    energyUsedKwh: 12.18,
    regenKwh: 0.63,
    efficiencyKwhPer100Km: 16.4,
    averageSpeedKph: 90.8,
    quality: {
      coveragePct: 100,
      displayedSamples: 33,
      expectedSamples: 33,
      unexpectedGapCount: 0,
      outOfRangeValuesIgnored: 0,
    },
    thermalRiseC: 4.4,
    powerScale: 23,
    phase: 2.9,
  }),
];

export const MODEL_EVALUATION = {
  syntheticTrips: 16,
  testTrips: 8,
  telemetrySamples: 1_908,
  rangeLabMaeKwh: 0.3414,
  baselineMaeKwh: 0.348,
  improvementPct: 1.9,
  splitLabel: "Walk-forward evaluation on 8 synthetic trips",
};
