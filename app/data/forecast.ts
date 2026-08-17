/**
 * Exact TypeScript port of backend/src/rangelab/forecast.py's engineering
 * fallback path when no eligible personal trips are supplied.
 */

export const ENGINEERING_FALLBACK_COEFFICIENTS = {
  interceptKwh: 0.05,
  distanceKwhPerKm: 0.155,
  coldDistanceKwhPerKmPer10C: 0.04,
  hotDistanceKwhPerKmPer10C: 0.018,
  speedDistanceKwhPerKm: 0.028,
  hvacProxyMultiplier: 0.9,
} as const;

export const ENGINEERING_FALLBACK_RESIDUAL_STD_KWH = 0.45;
export const EMPTY_HISTORY_BASELINE_KWH_PER_KM = 0.18;

export type EngineeringForecastInput = {
  distanceKm: number;
  ambientTempC: number;
  expectedSpeedKph: number;
  startingSocPct?: number;
  hvacPowerKw?: number;
  usableCapacityKwh?: number;
  residualStdKwh?: number;
};

export type EngineeringForecastResult = {
  predictedEnergyKwh: number;
  baselineEnergyKwh: number;
  lowerKwh: number;
  upperKwh: number;
  confidencePct: null;
  calibrated: false;
  predictedArrivalSocPct: number | null;
  bestArrivalSocPct: number | null;
  worstArrivalSocPct: number | null;
  efficiencyKwhPer100Km: number;
  modelKind: "engineering_fallback";
  trainingTripCount: 0;
  contributionsKwh: {
    intercept_kwh: number;
    distance_kwh_per_km: number;
    cold_distance_kwh_per_km_per_10c: number;
    hot_distance_kwh_per_km_per_10c: number;
    speed_distance_kwh_per_km: number;
    hvac_proxy_multiplier: number;
  };
};

const clamp = (value: number, minimum: number, maximum: number) =>
  Math.max(minimum, Math.min(maximum, value));

export function calculateEngineeringForecast({
  distanceKm,
  ambientTempC,
  expectedSpeedKph,
  startingSocPct,
  hvacPowerKw = 0,
  usableCapacityKwh = 60,
  residualStdKwh = ENGINEERING_FALLBACK_RESIDUAL_STD_KWH,
}: EngineeringForecastInput): EngineeringForecastResult {
  if (distanceKm <= 0) throw new RangeError("distanceKm must be greater than zero");
  if (expectedSpeedKph <= 0) throw new RangeError("expectedSpeedKph must be greater than zero");
  if (hvacPowerKw < 0) throw new RangeError("hvacPowerKw cannot be negative");
  if (usableCapacityKwh <= 0) throw new RangeError("usableCapacityKwh must be greater than zero");
  if (residualStdKwh < 0) throw new RangeError("residualStdKwh cannot be negative");

  const cold = Math.max(0, 18 - ambientTempC) / 10;
  const hot = Math.max(0, ambientTempC - 24) / 10;
  const speedPenalty = ((expectedSpeedKph - 55) / 55) ** 2;
  const durationHours = distanceKm / Math.max(expectedSpeedKph, 5);
  const coefficients = ENGINEERING_FALLBACK_COEFFICIENTS;
  const contributionsKwh = {
    intercept_kwh: coefficients.interceptKwh,
    distance_kwh_per_km: coefficients.distanceKwhPerKm * distanceKm,
    cold_distance_kwh_per_km_per_10c:
      coefficients.coldDistanceKwhPerKmPer10C * distanceKm * cold,
    hot_distance_kwh_per_km_per_10c:
      coefficients.hotDistanceKwhPerKmPer10C * distanceKm * hot,
    speed_distance_kwh_per_km:
      coefficients.speedDistanceKwhPerKm * distanceKm * speedPenalty,
    hvac_proxy_multiplier: coefficients.hvacProxyMultiplier * hvacPowerKw * durationHours,
  };
  const predictedEnergyKwh = Math.max(
    0,
    Object.values(contributionsKwh).reduce((total, contribution) => total + contribution, 0),
  );
  const baselineEnergyKwh = distanceKm * EMPTY_HISTORY_BASELINE_KWH_PER_KM;
  const distanceScale = Math.sqrt(Math.max(1, distanceKm / 20));
  const halfWidth = 1.282 * residualStdKwh * distanceScale;
  const lowerKwh = Math.max(0, predictedEnergyKwh - halfWidth);
  const upperKwh = predictedEnergyKwh + halfWidth;
  const predictedArrivalSocPct =
    startingSocPct === undefined
      ? null
      : clamp(startingSocPct - (predictedEnergyKwh / usableCapacityKwh) * 100, 0, 100);
  const bestArrivalSocPct =
    startingSocPct === undefined
      ? null
      : clamp(startingSocPct - (lowerKwh / usableCapacityKwh) * 100, 0, 100);
  const worstArrivalSocPct =
    startingSocPct === undefined
      ? null
      : clamp(startingSocPct - (upperKwh / usableCapacityKwh) * 100, 0, 100);

  return {
    predictedEnergyKwh,
    baselineEnergyKwh,
    lowerKwh,
    upperKwh,
    confidencePct: null,
    calibrated: false,
    predictedArrivalSocPct,
    bestArrivalSocPct,
    worstArrivalSocPct,
    efficiencyKwhPer100Km: (predictedEnergyKwh / distanceKm) * 100,
    modelKind: "engineering_fallback",
    trainingTripCount: 0,
    contributionsKwh,
  };
}

export function calculateScenario(
  distance: number,
  temperature: number,
  speed: number,
  startSoc: number,
) {
  return calculateEngineeringForecast({
    distanceKm: distance,
    ambientTempC: temperature,
    expectedSpeedKph: speed,
    startingSocPct: startSoc,
  });
}

/** Rounded values emitted by the Python API for cross-language regression tests. */
export const ENGINEERING_FORECAST_GOLDEN_CASES = [
  {
    name: "cold highway with HVAC",
    input: {
      distanceKm: 100,
      ambientTempC: -10,
      expectedSpeedKph: 90,
      hvacPowerKw: 3,
      startingSocPct: 90,
    },
    expectedBackendRounded: {
      predictedEnergyKwh: 30.884,
      baselineEnergyKwh: 18,
      lowerKwh: 29.594,
      upperKwh: 32.174,
      predictedArrivalSocPct: 38.5,
      confidencePct: null,
      calibrated: false,
    },
  },
  {
    name: "cold mixed-speed default HVAC",
    input: {
      distanceKm: 80,
      ambientTempC: -5,
      expectedSpeedKph: 85,
      hvacPowerKw: 0,
      startingSocPct: 80,
    },
    expectedBackendRounded: {
      predictedEnergyKwh: 20.476,
      baselineEnergyKwh: 14.4,
      lowerKwh: 19.323,
      upperKwh: 21.63,
      predictedArrivalSocPct: 45.9,
      confidencePct: null,
      calibrated: false,
    },
  },
] as const;
