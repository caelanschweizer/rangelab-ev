import assert from "node:assert/strict";
import test from "node:test";

import {
  ENGINEERING_FORECAST_GOLDEN_CASES,
  calculateEngineeringForecast,
} from "../app/data/forecast.ts";

const rounded = (value, digits) => Number(value.toFixed(digits));

test("engineering forecast matches backend golden cases", () => {
  for (const testCase of ENGINEERING_FORECAST_GOLDEN_CASES) {
    const actual = calculateEngineeringForecast(testCase.input);
    assert.equal(
      rounded(actual.predictedEnergyKwh, 3),
      testCase.expectedBackendRounded.predictedEnergyKwh,
      `${testCase.name}: predicted energy`,
    );
    assert.equal(
      rounded(actual.baselineEnergyKwh, 3),
      testCase.expectedBackendRounded.baselineEnergyKwh,
      `${testCase.name}: baseline`,
    );
    assert.equal(
      rounded(actual.lowerKwh, 3),
      testCase.expectedBackendRounded.lowerKwh,
      `${testCase.name}: lower heuristic band`,
    );
    assert.equal(
      rounded(actual.upperKwh, 3),
      testCase.expectedBackendRounded.upperKwh,
      `${testCase.name}: upper heuristic band`,
    );
    assert.equal(
      rounded(actual.predictedArrivalSocPct, 1),
      testCase.expectedBackendRounded.predictedArrivalSocPct,
      `${testCase.name}: arrival charge`,
    );
    assert.equal(actual.confidencePct, null, `${testCase.name}: no confidence claim`);
    assert.equal(actual.calibrated, false, `${testCase.name}: not calibrated`);
  }
});

test("forecast validates physical input bounds", () => {
  assert.throws(
    () =>
      calculateEngineeringForecast({
        distanceKm: 0,
        ambientTempC: 0,
        expectedSpeedKph: 60,
      }),
    /distanceKm/,
  );
  assert.throws(
    () =>
      calculateEngineeringForecast({
        distanceKm: 50,
        ambientTempC: 0,
        expectedSpeedKph: 60,
        hvacPowerKw: -1,
      }),
    /hvacPowerKw/,
  );
});
