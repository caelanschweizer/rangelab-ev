"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  calculateEngineeringForecast,
  calculateScenario,
} from "@/app/data/forecast";
import {
  MODEL_EVALUATION,
  SAMPLE_TRIPS,
  type TelemetryPoint,
  type TelemetryTrip,
} from "@/app/data/trips";
import styles from "./RangeLabDashboard.module.css";

export {
  calculateEngineeringForecast,
  calculateScenario,
  ENGINEERING_FORECAST_GOLDEN_CASES,
} from "@/app/data/forecast";

const formatTemperature = (value: number) =>
  `${value < 0 ? "−" : ""}${Math.abs(value).toFixed(0)}°C`;

const formatNumber = (value: number, digits = 1) => value.toFixed(digits);

type TimelineChartProps = {
  label: string;
  unit: string;
  kind: "power" | "soc" | "temperature";
  points: TelemetryPoint[];
  activeIndex: number;
  value: (point: TelemetryPoint) => number;
  formatValue: (value: number) => string;
};

function TimelineChart({
  label,
  unit,
  kind,
  points,
  activeIndex,
  value,
  formatValue,
}: TimelineChartProps) {
  const values = points.map(value);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = Math.max(1, maximum - minimum);
  const activeValue = values[activeIndex];

  return (
    <div className={styles.timelineRow}>
      <div className={styles.timelineLabel}>
        <span>{label}</span>
        <strong>{formatValue(activeValue)}</strong>
      </div>
      <div
        className={styles.timelinePlot}
        role="img"
        aria-label={`${label} timeline. Current value ${formatValue(activeValue)}. Range ${formatValue(minimum)} to ${formatValue(maximum)}.`}
      >
        <span className={styles.gridLineTop} aria-hidden="true" />
        <span className={styles.gridLineMiddle} aria-hidden="true" />
        {points.map((point, index) => {
          const pointValue = value(point);
          const isActive = index === activeIndex;

          if (kind === "power") {
            const size = Math.min(45, Math.max(4, (Math.abs(pointValue) / 36) * 45));
            const powerStyle = { "--bar-size": `${size}%` } as CSSProperties;
            return (
              <span
                className={`${styles.timelineCell} ${isActive ? styles.activeCell : ""}`}
                key={`${label}-${index}`}
                aria-hidden="true"
              >
                <span
                  className={`${styles.powerBar} ${
                    pointValue < 0 ? styles.regenBar : styles.drawBar
                  }`}
                  style={powerStyle}
                />
              </span>
            );
          }

          const normalizedHeight = 13 + ((pointValue - minimum) / span) * 70;
          const barStyle = { "--bar-size": `${normalizedHeight}%` } as CSSProperties;
          return (
            <span
              className={`${styles.timelineCell} ${isActive ? styles.activeCell : ""}`}
              key={`${label}-${index}`}
              aria-hidden="true"
            >
              <span
                className={`${styles.signalBar} ${
                  kind === "soc" ? styles.socBar : styles.temperatureBar
                }`}
                style={barStyle}
              />
            </span>
          );
        })}
      </div>
      <span className={styles.timelineUnit}>{unit}</span>
    </div>
  );
}

type MetricCardProps = {
  eyebrow: string;
  value: string;
  detail: string;
  accent: "lime" | "cyan" | "amber" | "neutral";
};

function MetricCard({ eyebrow, value, detail, accent }: MetricCardProps) {
  return (
    <article className={`${styles.metricCard} ${styles[accent]}`}>
      <span>{eyebrow}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

type ScenarioControlProps = {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  displayValue: string;
  onChange: (value: number) => void;
};

function ScenarioControl({
  id,
  label,
  value,
  min,
  max,
  step,
  displayValue,
  onChange,
}: ScenarioControlProps) {
  const fill = ((value - min) / (max - min)) * 100;
  const trackStyle = { "--range-fill": `${fill}%` } as CSSProperties;

  return (
    <div className={styles.scenarioControl}>
      <div className={styles.controlHeading}>
        <label htmlFor={id}>{label}</label>
        <output htmlFor={id}>{displayValue}</output>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        style={trackStyle}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <div className={styles.rangeBounds} aria-hidden="true">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}

export default function RangeLabDashboard() {
  const [selectedTripId, setSelectedTripId] = useState(SAMPLE_TRIPS[0].id);
  const [playbackIndex, setPlaybackIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [distance, setDistance] = useState(80);
  const [temperature, setTemperature] = useState(-5);
  const [speed, setSpeed] = useState(85);
  const [startSoc, setStartSoc] = useState(80);

  const selectedTrip =
    SAMPLE_TRIPS.find((trip) => trip.id === selectedTripId) ?? SAMPLE_TRIPS[0];
  const activePoint = selectedTrip.points[playbackIndex] ?? selectedTrip.points[0];
  const playbackPct = (playbackIndex / (selectedTrip.points.length - 1)) * 100;

  const scenario = useMemo(
    () => calculateScenario(distance, temperature, speed, startSoc),
    [distance, temperature, speed, startSoc],
  );
  const selectedTripFallback = calculateEngineeringForecast({
    distanceKm: selectedTrip.distanceKm,
    ambientTempC: selectedTrip.ambientC,
    expectedSpeedKph: selectedTrip.averageSpeedKph,
    startingSocPct: selectedTrip.startSoc,
  });

  useEffect(() => {
    if (!isPlaying) return;

    const timer = window.setInterval(() => {
      setPlaybackIndex((currentIndex) => {
        if (currentIndex >= selectedTrip.points.length - 1) {
          setIsPlaying(false);
          return currentIndex;
        }
        return currentIndex + 1;
      });
    }, 460);

    return () => window.clearInterval(timer);
  }, [isPlaying, selectedTrip.points.length]);

  const chooseTrip = (trip: TelemetryTrip) => {
    setSelectedTripId(trip.id);
    setPlaybackIndex(0);
    setIsPlaying(false);
  };

  const togglePlayback = () => {
    if (playbackIndex >= selectedTrip.points.length - 1) {
      setPlaybackIndex(0);
      setIsPlaying(true);
      return;
    }
    setIsPlaying((playing) => !playing);
  };

  const comparisonMax =
    Math.max(
      selectedTrip.energyUsedKwh,
      selectedTripFallback.predictedEnergyKwh,
      selectedTripFallback.baselineEnergyKwh,
    ) * 1.15;

  const scenarioWorstArrival = scenario.worstArrivalSocPct ?? 0;
  const scenarioBestArrival = scenario.bestArrivalSocPct ?? 0;
  const scenarioArrival = scenario.predictedArrivalSocPct ?? 0;
  const arrivalStatus =
    scenarioWorstArrival < 5
      ? { label: "Charging stop likely", tone: styles.risk }
      : scenarioWorstArrival < 15
        ? { label: "Low-charge arrival", tone: styles.caution }
        : { label: "Comfortable reserve", tone: styles.safe };

  return (
    <div className={styles.dashboard}>
      <header className={styles.header}>
        <a className={styles.brand} href="#overview" aria-label="RangeLab EV overview">
          <span className={styles.brandMark} aria-hidden="true">
            R
          </span>
          <span>
            RangeLab <b>EV</b>
          </span>
        </a>
        <nav className={styles.nav} aria-label="Primary navigation">
          <a href="#trip-replay">Trip replay</a>
          <a href="#forecast-lab">Forecast lab</a>
          <a href="#methodology">Method</a>
        </nav>
        <a className={styles.headerCta} href="#trip-replay">
          Explore the data <span aria-hidden="true">↓</span>
        </a>
      </header>

      <main>
        <section className={styles.hero} id="overview">
          <div className={styles.heroCopy}>
            <div className={styles.projectLabel}>
              <span className={styles.liveDot} aria-hidden="true" />
              Open-source vehicle intelligence
            </div>
            <h1>
              Every kilowatt-hour, <em>accounted for.</em>
            </h1>
            <p>
              A synthetic-first telemetry lab that turns read-only, Bolt-like signals into
              trip insights, visible data checks, and transparent arrival-charge forecasts.
            </p>
            <div className={styles.heroActions}>
              <a className={styles.primaryButton} href="#trip-replay">
                Replay a sample trip <span aria-hidden="true">→</span>
              </a>
              <a className={styles.textLink} href="#methodology">
                Inspect the methodology
              </a>
            </div>
          </div>

          <aside className={styles.signalPanel} aria-label="Project highlights">
            <div className={styles.signalOrb} aria-hidden="true">
              <span>60</span>
              <small>kWh</small>
            </div>
            <dl className={styles.heroStats}>
              <div>
                <dt>{MODEL_EVALUATION.telemetrySamples.toLocaleString()}</dt>
                <dd>benchmark rows</dd>
              </div>
              <div>
                <dt>{MODEL_EVALUATION.rangeLabMaeKwh.toFixed(4)} kWh</dt>
                <dd>synthetic MAE</dd>
              </div>
              <div>
                <dt>{MODEL_EVALUATION.improvementPct}%</dt>
                <dd>vs. baseline</dd>
              </div>
            </dl>
          </aside>
        </section>

        <section className={styles.trustStrip} aria-label="Demo data and safety notices">
          <div>
            <span className={styles.trustIcon} aria-hidden="true">S</span>
            <p><strong>Four-trip UI fixture</strong> 132 generated chart points; no live vehicle connected.</p>
          </div>
          <div>
            <span className={styles.trustIcon} aria-hidden="true">R</span>
            <p><strong>Read-only by design</strong> The pipeline never sends vehicle commands.</p>
          </div>
          <div>
            <span className={styles.trustIcon} aria-hidden="true">P</span>
            <p><strong>Synthetic, not anonymized</strong> Generated from scratch with no owner, VIN, or GPS data.</p>
          </div>
        </section>

        <section className={styles.section} id="trip-replay">
          <div className={styles.sectionIntro}>
            <div>
              <p className={styles.eyebrow}>01 / Trip intelligence</p>
              <h2>See the drive, sample by sample.</h2>
            </div>
            <p>
              Scrub through synchronized power, charge, and thermal signals. Negative power
              marks energy recovered through regenerative braking. All public trip values are synthetic.
            </p>
          </div>

          <div className={styles.tripPicker} role="group" aria-label="Choose a sample trip">
            {SAMPLE_TRIPS.map((trip) => (
              <button
                type="button"
                key={trip.id}
                className={trip.id === selectedTrip.id ? styles.selectedTrip : ""}
                aria-pressed={trip.id === selectedTrip.id}
                onClick={() => chooseTrip(trip)}
              >
                <span>{trip.shortLabel}</span>
                <small>{formatTemperature(trip.ambientC)} · {trip.distanceKm} km</small>
              </button>
            ))}
          </div>

          <div className={styles.replayGrid}>
            <article className={styles.telemetryPanel}>
              <div className={styles.tripHeading}>
                <div>
                  <div className={styles.tripMeta}>
                    <span>{selectedTrip.dateLabel}</span>
                    <span>{selectedTrip.condition}</span>
                  </div>
                  <h3>{selectedTrip.routeLabel}</h3>
                  <p>{selectedTrip.description}</p>
                </div>
                <span className={styles.demoPill}>Synthetic UI fixture</span>
              </div>

              <div className={styles.playbackReadout}>
                <div>
                  <span>Elapsed</span>
                  <strong>{activePoint.elapsedMinutes}<small> min</small></strong>
                </div>
                <div>
                  <span>Distance</span>
                  <strong>{formatNumber(activePoint.distanceKm)}<small> km</small></strong>
                </div>
                <div>
                  <span>Speed</span>
                  <strong>{activePoint.speedKph}<small> km/h</small></strong>
                </div>
                <div>
                  <span>Net energy</span>
                  <strong>{activePoint.cumulativeEnergyKwh.toFixed(2)}<small> kWh</small></strong>
                </div>
              </div>

              <div className={styles.timelineStack}>
                <TimelineChart
                  label="Battery power"
                  unit="draw / regen"
                  kind="power"
                  points={selectedTrip.points}
                  activeIndex={playbackIndex}
                  value={(point) => point.powerKw}
                  formatValue={(value) => `${value > 0 ? "+" : ""}${formatNumber(value)} kW`}
                />
                <TimelineChart
                  label="State of charge"
                  unit="usable charge"
                  kind="soc"
                  points={selectedTrip.points}
                  activeIndex={playbackIndex}
                  value={(point) => point.socPct}
                  formatValue={(value) => `${formatNumber(value)}%`}
                />
                <TimelineChart
                  label="Battery temperature"
                  unit="pack average"
                  kind="temperature"
                  points={selectedTrip.points}
                  activeIndex={playbackIndex}
                  value={(point) => point.batteryTempC}
                  formatValue={formatTemperature}
                />
              </div>

              <div className={styles.transport}>
                <button
                  type="button"
                  className={styles.playButton}
                  onClick={togglePlayback}
                  aria-label={isPlaying ? "Pause trip playback" : "Play trip playback"}
                >
                  <span aria-hidden="true">{isPlaying ? "Ⅱ" : "▶"}</span>
                </button>
                <span className={styles.visuallyHidden} role="status" aria-live="polite">
                  {isPlaying ? "Trip playback running." : "Trip playback paused."}
                </span>
                <label className={styles.scrubberLabel}>
                  <span className={styles.visuallyHidden}>Trip playback position</span>
                  <input
                    type="range"
                    min={0}
                    max={selectedTrip.points.length - 1}
                    value={playbackIndex}
                    aria-valuetext={`${activePoint.elapsedMinutes} of ${selectedTrip.durationMinutes} minutes`}
                    style={{ "--range-fill": `${playbackPct}%` } as CSSProperties}
                    onChange={(event) => {
                      setPlaybackIndex(Number(event.target.value));
                      setIsPlaying(false);
                    }}
                  />
                </label>
                <span className={styles.transportTime}>
                  {activePoint.elapsedMinutes}:00 / {selectedTrip.durationMinutes}:00
                </span>
              </div>
            </article>

            <aside className={styles.qualityPanel}>
              <div className={styles.panelHeading}>
                <div>
                  <p className={styles.eyebrow}>Fixture report</p>
                  <h3>UI fixture integrity</h3>
                </div>
                <span className={styles.qualityScore}>{selectedTrip.quality.coveragePct}%</span>
              </div>
              <div className={styles.qualityMeter} aria-label={`${selectedTrip.quality.coveragePct}% of expected chart points present`}>
                <span style={{ width: `${selectedTrip.quality.coveragePct}%` }} />
              </div>
              <dl className={styles.qualityList}>
                <div>
                  <dt>Chart points present</dt>
                  <dd>{selectedTrip.quality.displayedSamples} / {selectedTrip.quality.expectedSamples}</dd>
                </div>
                <div>
                  <dt>Unexpected gaps detected</dt>
                  <dd>{selectedTrip.quality.unexpectedGapCount}</dd>
                </div>
                <div>
                  <dt>Out-of-range values ignored</dt>
                  <dd>{selectedTrip.quality.outOfRangeValuesIgnored}</dd>
                </div>
                <div>
                  <dt>Personal coordinates</dt>
                  <dd className={styles.privateValue}>Not generated</dd>
                </div>
              </dl>
              <div className={styles.qualityNote}>
                <span aria-hidden="true">✓</span>
                <p><strong>Fixture bounds checked</strong> Every displayed value is within the UI fixture&apos;s documented ranges.</p>
              </div>
            </aside>
          </div>

          <div className={styles.metricGrid}>
            <MetricCard
              eyebrow="Net energy used"
              value={`${selectedTrip.energyUsedKwh.toFixed(2)} kWh`}
              detail={`${selectedTrip.durationMinutes} minutes recorded`}
              accent="cyan"
            />
            <MetricCard
              eyebrow="Trip efficiency"
              value={`${selectedTrip.efficiencyKwhPer100Km.toFixed(1)}`}
              detail="kWh / 100 km"
              accent="lime"
            />
            <MetricCard
              eyebrow="Regen recovered"
              value={`${selectedTrip.regenKwh.toFixed(2)} kWh`}
              detail={`${((selectedTrip.regenKwh / selectedTrip.energyUsedKwh) * 100).toFixed(0)}% of net trip energy`}
              accent="amber"
            />
            <MetricCard
              eyebrow="Arrival charge"
              value={`${selectedTrip.endSoc}%`}
              detail={`Started at ${selectedTrip.startSoc}%`}
              accent="neutral"
            />
          </div>
        </section>

        <section className={`${styles.section} ${styles.modelSection}`} id="methodology">
          <div className={styles.sectionIntro}>
            <div>
              <p className={styles.eyebrow}>02 / Honest forecasting</p>
              <h2>A model has to beat something.</h2>
            </div>
            <p>
              A separate 16-trip, 1,908-row synthetic benchmark uses walk-forward splits against
              a distance-only baseline. Real Bolt validation begins when owner logs arrive.
            </p>
          </div>

          <div className={styles.modelGrid}>
            <article className={styles.comparisonPanel}>
              <div className={styles.comparisonHeader}>
                <div>
                  <span>Four-trip UI fixture · zero-history engineering fallback</span>
                  <h3>{selectedTrip.shortLabel}</h3>
                </div>
                <span className={styles.actualBadge}>Fixture target {selectedTrip.energyUsedKwh.toFixed(2)} kWh</span>
              </div>
              <div className={styles.comparisonRows}>
                {[
                  { label: "Fixture target", value: selectedTrip.energyUsedKwh, className: styles.actualBar },
                  { label: "Fallback", value: selectedTripFallback.predictedEnergyKwh, className: styles.modelBar },
                  { label: "Empty-history baseline", value: selectedTripFallback.baselineEnergyKwh, className: styles.baselineBar },
                ].map((row) => (
                  <div className={styles.comparisonRow} key={row.label}>
                    <span>{row.label}</span>
                    <div className={styles.comparisonTrack}>
                      <i
                        className={row.className}
                        style={{ width: `${(row.value / comparisonMax) * 100}%` }}
                      />
                    </div>
                    <strong>{row.value.toFixed(2)}</strong>
                  </div>
                ))}
              </div>
              <div className={styles.intervalNote}>
                <span className={styles.intervalLine} aria-hidden="true" />
                Heuristic fallback band: {selectedTripFallback.lowerKwh.toFixed(2)}–{selectedTripFallback.upperKwh.toFixed(2)} kWh, using an assumed 0.45 kWh residual scale
              </div>
            </article>

            <aside className={styles.evaluationPanel}>
              <p className={styles.eyebrow}>Synthetic walk-forward evaluation</p>
              <div className={styles.improvementValue}>
                <strong>−{MODEL_EVALUATION.improvementPct}%</strong>
                <span>mean absolute error</span>
              </div>
              <dl className={styles.evaluationStats}>
                <div>
                  <dt>RangeLab MAE</dt>
                  <dd>{MODEL_EVALUATION.rangeLabMaeKwh} kWh</dd>
                </div>
                <div>
                  <dt>Baseline MAE</dt>
                  <dd>{MODEL_EVALUATION.baselineMaeKwh} kWh</dd>
                </div>
                <div>
                  <dt>Benchmark</dt>
                  <dd>{MODEL_EVALUATION.syntheticTrips} trips / {MODEL_EVALUATION.testTrips} evaluated</dd>
                </div>
              </dl>
              <p className={styles.evaluationFootnote}>
                {MODEL_EVALUATION.splitLabel}. Reproducible demo evidence only; real-world accuracy is not yet claimed.
              </p>
            </aside>
          </div>
        </section>

        <section className={`${styles.section} ${styles.forecastSection}`} id="forecast-lab">
          <div className={styles.sectionIntro}>
            <div>
              <p className={styles.eyebrow}>03 / Scenario planner</p>
              <h2>Pressure-test the next drive.</h2>
            </div>
            <p>
              Change the conditions to see how distance, temperature, and speed affect
              expected consumption and arrival charge.
            </p>
          </div>

          <div className={styles.planner}>
            <div className={styles.plannerControls}>
              <ScenarioControl
                id="distance"
                label="Trip distance"
                value={distance}
                min={10}
                max={300}
                step={5}
                displayValue={`${distance} km`}
                onChange={setDistance}
              />
              <ScenarioControl
                id="temperature"
                label="Outside temperature"
                value={temperature}
                min={-25}
                max={35}
                step={1}
                displayValue={formatTemperature(temperature)}
                onChange={setTemperature}
              />
              <ScenarioControl
                id="speed"
                label="Average speed"
                value={speed}
                min={30}
                max={115}
                step={5}
                displayValue={`${speed} km/h`}
                onChange={setSpeed}
              />
              <ScenarioControl
                id="start-soc"
                label="Starting charge"
                value={startSoc}
                min={20}
                max={100}
                step={5}
                displayValue={`${startSoc}%`}
                onChange={setStartSoc}
              />
            </div>

            <div className={styles.forecastResult}>
              <div className={styles.resultTopline}>
                <span>Backend-matched zero-history fallback</span>
                <span className={arrivalStatus.tone}>{arrivalStatus.label}</span>
              </div>
              <div className={styles.energyPrediction}>
                <strong>{scenario.predictedEnergyKwh.toFixed(1)}</strong>
                <span>kWh predicted</span>
              </div>
              <div className={styles.uncertaintyRange}>
                <div>
                  <span>Heuristic energy band</span>
                  <strong>{scenario.lowerKwh.toFixed(1)}–{scenario.upperKwh.toFixed(1)} kWh</strong>
                </div>
                <div>
                  <span>Expected efficiency</span>
                  <strong>{scenario.efficiencyKwhPer100Km.toFixed(1)} kWh / 100 km</strong>
                </div>
              </div>
              <div className={styles.arrivalCard}>
                <div className={styles.chargeRing} style={{ "--charge": `${scenarioArrival}%` } as CSSProperties}>
                  <span>{scenarioArrival.toFixed(0)}%</span>
                </div>
                <div>
                  <span>Predicted arrival charge</span>
                  <strong>
                    {scenarioWorstArrival.toFixed(0)}–{scenarioBestArrival.toFixed(0)}%
                  </strong>
                  <small>Zero-history engineering fallback with 0 kW HVAC input. The band assumes a 0.45 kWh residual scale; it is not empirically calibrated or a safety guarantee.</small>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className={styles.pipelineSection} aria-labelledby="pipeline-title">
          <div>
            <p className={styles.eyebrow}>Built end to end</p>
            <h2 id="pipeline-title">From raw signal to defensible insight.</h2>
          </div>
          <ol className={styles.pipeline}>
            <li><span>01</span><strong>Ingest</strong><small>CSV / OBD-II logs</small></li>
            <li><span>02</span><strong>Validate</strong><small>Typed signal schema</small></li>
            <li><span>03</span><strong>Analyze</strong><small>Trip + quality engine</small></li>
            <li><span>04</span><strong>Forecast</strong><small>Baseline-tested model</small></li>
          </ol>
          <p className={styles.stackLine}>
            FastAPI <i>·</i> PostgreSQL <i>·</i> Python <i>·</i> React + TypeScript <i>·</i> Docker <i>·</i> GitHub Actions
          </p>
        </section>
      </main>

      <footer className={styles.footer}>
        <div className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true">R</span>
          <span>RangeLab <b>EV</b></span>
        </div>
        <p>Open-source EV telemetry · Built around a 2018 Chevrolet Bolt Premier</p>
        <a href="#overview">Back to top ↑</a>
      </footer>
    </div>
  );
}
