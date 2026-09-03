import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
function App() {
  const [data, setData] = useState(null);
  const [remediation, setRemediation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [topology, setTopology] = useState(null);
  const [topologyLoading, setTopologyLoading] = useState(false);
  const [recoveryLoading, setRecoveryLoading] = useState(false);
  const [error, setError] = useState(null);
  const investigationRef = useRef(null);

  const [showRcaReasoning, setShowRcaReasoning] = useState(false);
  const [trafficShift, setTrafficShift] = useState(60);

  const [failoverCapacity, setFailoverCapacity] = useState(80);
  const [retryBudget, setRetryBudget] = useState(10);
  const [recoveryVerification, setRecoveryVerification] = useState({
    status: "NOT_VERIFIED",
    startedAt: null,
    result: null,
  });
  const [evaluation, setEvaluation] = useState(null);
  const [evaluationLoading, setEvaluationLoading] = useState(false);
  const [evaluationError, setEvaluationError] = useState(null);
  // LIVE TELEMETRY
  const [liveTelemetry, setLiveTelemetry] = useState([]);
  const [telemetryLive, setTelemetryLive] = useState(false);
  const [liveTelemetryMeta, setLiveTelemetryMeta] = useState(null);

  // LIVE INCIDENT STATE
  const [liveIncident, setLiveIncident] = useState(null);
  const [liveIncidentStatus, setLiveIncidentStatus] = useState("CONNECTING");
  const [liveIncidentSeverity, setLiveIncidentSeverity] = useState("UNKNOWN");
  const [liveIncidentCause, setLiveIncidentCause] =
    useState("No active incident");

  // INCIDENT HISTORY
  const [incidentHistory, setIncidentHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  const analyzeIncident = async () => {
    setLoading(true);
    setError(null);
    setRemediation(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/incidents/investigate?window_minutes=60`,
      );

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const result = await response.json();

      const normalizedResult = {
        incident_analysis: result?.incident_analysis ?? result?.detection ?? {},

        root_cause_analysis:
          result?.root_cause_analysis ?? result?.root_cause ?? {},

        ai_investigation: result?.ai_investigation ?? {},
      };

      setTimeout(() => {
        investigationRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 100);

      setData(normalizedResult);
    } catch (err) {
      console.error(err);

      setError(
        "Unable to connect to PayLens backend. Make sure FastAPI is running.",
      );
    } finally {
      setLoading(false);
    }
  };

  const fetchTopology = async () => {
    setTopologyLoading(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/incidents/topology?window_minutes=60`,
      );

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const result = await response.json();

      setTopology(result);
    } catch (err) {
      console.error("Topology fetch failed:", err);
      setTopology(null);
    } finally {
      setTopologyLoading(false);
    }
  };

  const simulateRecovery = async () => {
    setRecoveryLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/incidents/remediation?window_minutes=60`,
      );

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const result = await response.json();

      setRemediation(result);
    } catch (err) {
      console.error(err);

      setError(
        "Unable to load remediation analysis. Make sure FastAPI is running.",
      );
    } finally {
      setRecoveryLoading(false);
    }
  };

  const verifyRecovery = async () => {
    setRecoveryLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/incidents/recovery-demo?window_minutes=60`,
      );

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const result = await response.json();
      const verification = result?.verification;

      if (!verification) {
        throw new Error("Recovery verification data was not returned.");
      }

      setRecoveryVerification({
        status:
          verification.failure_recovered && verification.latency_recovered
            ? "RECOVERY_VERIFIED"
            : "VERIFICATION_FAILED",

        startedAt: Date.now(),

        result: {
          observedFailureRate: verification.after?.failure_rate ?? 0,

          observedLatency: verification.after?.average_latency_ms ?? 0,

          failureImprovement:
            verification.improvement?.failure_rate_percent ?? 0,

          latencyImprovement: verification.improvement?.latency_percent ?? 0,

          failureRecovered: verification.failure_recovered ?? false,

          latencyRecovered: verification.latency_recovered ?? false,

          verifiedAt: new Date().toISOString(),
        },
      });
    } catch (err) {
      console.error(err);

      setRecoveryVerification({
        status: "VERIFICATION_FAILED",
        startedAt: Date.now(),
        result: {
          reason: "Unable to obtain recovery telemetry.",
        },
      });

      setError("Unable to verify recovery. Make sure FastAPI is running.");
    } finally {
      setRecoveryLoading(false);
    }
  };

  const startRecoveryVerification = () => {
    setRecoveryVerification({
      status: "VERIFYING",
      startedAt: Date.now(),
      result: null,
    });
  };

  const fetchIncidentHistory = async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/incidents/history?limit=20`,
      );

      if (!response.ok) {
        throw new Error(`History backend returned ${response.status}`);
      }

      const result = await response.json();

      setIncidentHistory(
        Array.isArray(result?.incidents) ? result.incidents : [],
      );
    } catch (err) {
      console.error("Incident history error:", err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const runEvaluation = async () => {
    setEvaluationLoading(true);
    setEvaluationError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/evaluation/run`);

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const result = await response.json();
      setEvaluation(result);
    } catch (err) {
      console.error(err);
      setEvaluationError(
        "Unable to run model evaluation. Make sure the evaluation-enabled FastAPI backend is running.",
      );
    } finally {
      setEvaluationLoading(false);
    }
  };

  useEffect(() => {
    analyzeIncident();
    fetchTopology();
  }, []);

  /*
   * LIVE INCIDENT + TELEMETRY STREAM
   *
   * /incidents/live is the source of truth for the current
   * operational incident state.
   *
   * /telemetry/live provides the detailed telemetry trend.
   */
  useEffect(() => {
    let interval;
    let mounted = true;

    const fetchLiveState = async () => {
      try {
        const [incidentResponse, telemetryResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/incidents/live?window_minutes=60`),
          fetch(`${API_BASE_URL}/telemetry/live?window_minutes=60`),
        ]);

        if (!incidentResponse.ok) {
          throw new Error(
            `Incident backend returned ${incidentResponse.status}`,
          );
        }

        if (!telemetryResponse.ok) {
          throw new Error(
            `Telemetry backend returned ${telemetryResponse.status}`,
          );
        }

        const incidentResult = await incidentResponse.json();
        const telemetryResult = await telemetryResponse.json();

        if (!mounted) return;

        /*
         * -------------------------------------------------------
         * LIVE INCIDENT STATE
         * -------------------------------------------------------
         */

        setLiveIncident(incidentResult);

        const status =
          incidentResult?.live_status || incidentResult?.status || "UNKNOWN";

        const severity =
          incident?.severity || liveIncidentSeverity || "UNKNOWN";

        const liveAnalysis = incidentResult?.incident?.analysis || {};
        const liveSignals = liveAnalysis?.dominant_signals || {};

        const cause =
          incidentResult?.root_cause ||
          incidentResult?.primary_root_cause ||
          incidentResult?.incident?.root_cause ||
          (liveSignals?.gateway
            ? `Gateway degradation · ${liveSignals.gateway}`
            : liveSignals?.error_code
              ? liveSignals.error_code
              : "Payment system degradation");

        setLiveIncidentStatus(String(status).toUpperCase());
        setLiveIncidentSeverity(String(severity).toUpperCase());
        setLiveIncidentCause(cause);

        /*
         * -------------------------------------------------------
         * LIVE TELEMETRY
         * -------------------------------------------------------
         */

        const metrics = telemetryResult?.metrics || {};
        const backendTrend = Array.isArray(telemetryResult?.trend)
          ? telemetryResult.trend
          : [];

        const trendSamples = backendTrend.map((sample, index) => ({
          id: `${sample.timestamp}-${index}`,
          failureRate: Number(sample.failure_rate ?? 0),
          latency: Number(
            sample.average_latency_ms ??
              sample.latency ??
              metrics.average_latency_ms ??
              0,
          ),
          events: Number(sample.events ?? 0),
          timestamp: new Date(sample.timestamp),
        }));

        setLiveTelemetry(trendSamples);
        setLiveTelemetryMeta(telemetryResult);

        /*
         * Prefer incident endpoint status when available.
         * Fall back to telemetry endpoint status.
         */
        const isLive =
          status === "INCIDENT_ACTIVE" ||
          status === "LIVE" ||
          telemetryResult?.status === "live";

        setTelemetryLive(isLive);
      } catch (err) {
        console.error("Live incident/telemetry error:", err);

        if (!mounted) return;

        setTelemetryLive(false);
        setLiveIncidentStatus("DISCONNECTED");
      }
    };

    fetchLiveState();
    fetchIncidentHistory();

    interval = setInterval(() => {
      fetchLiveState();
      fetchIncidentHistory();
    }, 5000);

    return () => {
      mounted = false;
      clearInterval(interval);
      setTelemetryLive(false);
    };
  }, []);

  /*
   * RECOVERY VERIFICATION
   *
   * Verification uses values from the existing data object
   * instead of render-time variables declared later in App().
   */
  useEffect(() => {
    if (recoveryVerification.status !== "VERIFYING") {
      return;
    }

    const startedAt = recoveryVerification.startedAt;

    if (!startedAt) {
      return;
    }

    const verificationWindowMs = 15000;
    const elapsed = Date.now() - startedAt;

    if (elapsed < verificationWindowMs) {
      return;
    }

    const currentMetrics = data?.incident_analysis?.current || {};

    const incidentFailureRate = Number(currentMetrics?.failure_rate ?? 0);

    const incidentLatency = Number(currentMetrics?.average_latency_ms ?? 0);

    const latestSample =
      liveTelemetry.length > 0 ? liveTelemetry[liveTelemetry.length - 1] : null;

    const observedFailureRate = Number(
      latestSample?.failureRate ??
        liveTelemetryMeta?.metrics?.failure_rate ??
        incidentFailureRate,
    );

    const observedLatency = Number(
      latestSample?.latency ??
        liveTelemetryMeta?.metrics?.average_latency_ms ??
        incidentLatency,
    );

    const failureImprovement =
      incidentFailureRate > 0
        ? ((incidentFailureRate - observedFailureRate) / incidentFailureRate) *
          100
        : 0;

    const latencyImprovement =
      incidentLatency > 0
        ? ((incidentLatency - observedLatency) / incidentLatency) * 100
        : 0;

    const failureRecovered = observedFailureRate < incidentFailureRate;

    const latencyRecovered = observedLatency < incidentLatency;

    const verified = failureRecovered && latencyRecovered;

    setRecoveryVerification({
      status: verified ? "RECOVERY_VERIFIED" : "VERIFICATION_FAILED",

      startedAt,

      result: {
        observedFailureRate,
        observedLatency,
        failureImprovement,
        latencyImprovement,
        failureRecovered,
        latencyRecovered,
        verifiedAt: new Date().toISOString(),
      },
    });
  }, [
    recoveryVerification.status,
    recoveryVerification.startedAt,
    data,
    liveTelemetry,
    liveTelemetryMeta,
  ]);

  /*
   * IMPORTANT:
   * Do not put hooks below this point.
   * All calculations below are normal JavaScript calculations.
   * This prevents:
   * "Rendered fewer hooks than expected"
   */

  if (loading && !data) {
    return (
      <div className="loading-screen">
        <div className="loading-box">
          <div className="loading-logo">P</div>

          <h2>PayLens AI</h2>

          <p>Analyzing payment telemetry...</p>

          <div className="loading-line">
            <span></span>
          </div>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="loading-screen">
        <div className="loading-box">
          <div className="loading-logo">P</div>

          <h2>PayLens AI</h2>

          <p>{error}</p>

          <button className="primary-button" onClick={analyzeIncident}>
            Retry Analysis
          </button>
        </div>
      </div>
    );
  }

  const incident = data?.incident_analysis || {};
  const rca = data?.root_cause_analysis || {};
  const ai = data?.ai_investigation || {};

  const current = incident?.current || {};
  const baseline = incident?.baseline || {};
  const changes = incident?.changes || {};
  const breakdowns = incident?.breakdowns || {};

  const primaryRootCause = rca?.primary_root_cause || {};

  const failureRate = Number(current?.failure_rate ?? 0);
  const latency = Number(current?.average_latency_ms ?? 0);
  const failedPayments = Number(current?.failed_events ?? 0);
  const failedValue = Number(current?.failed_transaction_value ?? 0);

  const baselineFailureRate = Number(baseline?.failure_rate ?? 0);
  const baselineLatency = Number(baseline?.average_latency_ms ?? 0);

  const currentEvents = Number(current?.events ?? 0);
  const baselineEvents = Number(baseline?.events ?? 0);

  const confidence = Number(primaryRootCause?.confidence ?? 0);

  const rootCause = primaryRootCause?.title || "No root cause identified";

  const rootCauseCode = primaryRootCause?.cause || "UNKNOWN";

  const severity = incident?.severity || "UNKNOWN";

  const incidentDetected =
    incident?.incident_detected === true ||
    liveIncidentStatus === "INCIDENT_ACTIVE";

  const evidence = Array.isArray(ai?.evidence) ? ai.evidence : [];

  const recommendations = Array.isArray(ai?.recommended_actions)
    ? ai.recommended_actions
    : [];

  const remediationRecommendations =
    remediation?.remediation?.recommendations || [];

  const hypotheses = Array.isArray(rca?.hypotheses) ? rca.hypotheses : [];

  const gatewayRates = breakdowns?.gateway_failure_rates || {};

  const issuerRates = breakdowns?.issuer_failure_rates || {};

  const paymentMethodRates = breakdowns?.payment_method_failure_rates || {};

  /*
   * Dominant telemetry signals.
   * Normal JS calculations only — no hooks.
   */

  const dominantGateway = getHighestEntry(gatewayRates);

  const dominantIssuer = getHighestEntry(issuerRates);

  const dominantPaymentMethod = getHighestEntry(paymentMethodRates);

  const dominantErrorCode = getDominantErrorCode(
    evidence,
    rootCauseCode,
    rootCause,
  );

  const latestTelemetry =
    liveTelemetry.length > 0
      ? liveTelemetry[liveTelemetry.length - 1]
      : {
          failureRate,
          latency,
          events: currentEvents,
        };

  const liveMetrics = liveTelemetryMeta?.metrics || {};
  const liveGatewayData = liveTelemetryMeta?.gateway || {};

  const liveFailureRate = Number(
    liveMetrics.failure_rate ??
      liveIncident?.failure_rate ??
      liveIncident?.metrics?.failure_rate ??
      latestTelemetry.failureRate ??
      0,
  );

  const liveLatency = Number(
    liveMetrics.average_latency_ms ??
      liveIncident?.average_latency_ms ??
      liveIncident?.metrics?.average_latency_ms ??
      latestTelemetry.latency ??
      0,
  );

  const liveEvents = Number(
    liveMetrics.events ??
      liveIncident?.events ??
      liveIncident?.metrics?.events ??
      latestTelemetry.events ??
      0,
  );

  const liveGateway =
    liveGatewayData.gateway ||
    liveIncident?.gateway ||
    liveIncident?.dominant_gateway ||
    dominantGateway?.key ||
    "gateway_b";

  const liveGatewayStatus =
    liveGatewayData.status ||
    liveIncident?.gateway_status ||
    (liveIncidentStatus === "INCIDENT_ACTIVE" ? "AT RISK" : "HEALTHY");

  const trendValues = liveTelemetry.map((sample) => sample.failureRate);

  const trendMax = Math.max(...trendValues, liveFailureRate, 1);

  const trendMin = Math.min(...trendValues, 0);

  /*
   * Interactive simulator.
   *
   * If backend recovery data exists, use it.
   * Otherwise create a conservative visual projection
   * from current telemetry.
   */

  const backendSimulation = remediation?.recovery_simulation || null;

  /*
   * Decision simulator is intentionally independent from the
   * backend recovery simulation.
   *
   * Backend remediation = recommended mitigation result.
   * Decision simulator = user-controlled what-if scenario.
   */
  const effectiveShift = Math.min(trafficShift, failoverCapacity);

  const capacityLimited = trafficShift > failoverCapacity;

  const simulatedFailureRate = calculateProjectedFailureRate(
    failureRate,
    baselineFailureRate,
    effectiveShift,
  );

  const simulatedLatency = calculateProjectedLatency(
    latency,
    baselineLatency,
    effectiveShift,
  );

  const retryRecovery = Math.min(0.12, (Number(retryBudget) / 100) * 0.4);

  const retryLoadPenalty = (Number(retryBudget) / 100) * 0.12;

  const retryAdjustedFailureRate = Math.max(
    baselineFailureRate,
    simulatedFailureRate -
      simulatedFailureRate * retryRecovery +
      failureRate * retryLoadPenalty,
  );

  const retryAdjustedLatency = simulatedLatency * (1 + retryLoadPenalty);

  const retryRecoveredTransactions = Math.round(
    failedPayments *
      Math.max(
        0,
        (simulatedFailureRate - retryAdjustedFailureRate) /
          Math.max(simulatedFailureRate, 0.01),
      ),
  );

  const failureReduction = Math.max(0, failureRate - retryAdjustedFailureRate);

  const latencyReduction = Math.max(0, latency - retryAdjustedLatency);

  const estimatedRecovered = Math.round(
    failedPayments * (failureReduction / Math.max(failureRate, 0.01)),
  );

  const averageFailedTransactionValue =
    failedPayments > 0 ? failedValue / failedPayments : 0;

  const analysisWindowMinutes = Number(incident?.analysis_window_minutes ?? 60);

  const transactionValueAtRisk = failedValue;

  const valueAtRiskPerMinute =
    analysisWindowMinutes > 0
      ? transactionValueAtRisk / analysisWindowMinutes
      : 0;

  const projectedRecoveredValue =
    averageFailedTransactionValue * estimatedRecovered;

  const recoveryValuePercent =
    transactionValueAtRisk > 0
      ? (projectedRecoveredValue / transactionValueAtRisk) * 100
      : 0;

  const recoveryScore = Math.max(
    0,
    Math.min(
      100,
      Math.round(
        (failureReduction / Math.max(failureRate, 0.01)) * 70 +
          (latencyReduction / Math.max(latency, 1)) * 30 -
          retryLoadPenalty * 25,
      ),
    ),
  );

  const decisionOutcome = capacityLimited
    ? "CAPACITY CONSTRAINED"
    : recoveryScore >= 75
      ? "STRONG MITIGATION"
      : recoveryScore >= 50
        ? "MODERATE MITIGATION"
        : "LIMITED RECOVERY";

  /*
   * Find the strongest feasible configuration.
   * We evaluate realistic 5% increments for traffic shift
   * and retry budget while respecting failover capacity.
   */
  let bestConfiguration = null;

  for (let shift = 0; shift <= 100; shift += 5) {
    const feasibleShift = Math.min(shift, failoverCapacity);

    const projectedFailure = calculateProjectedFailureRate(
      failureRate,
      baselineFailureRate,
      feasibleShift,
    );

    const projectedLatency = calculateProjectedLatency(
      latency,
      baselineLatency,
      feasibleShift,
    );

    for (let retry = 0; retry <= 30; retry += 5) {
      const recovery = Math.min(0.12, (retry / 100) * 0.4);

      const loadPenalty = (retry / 100) * 0.12;

      const finalFailureRate = Math.max(
        baselineFailureRate,
        projectedFailure -
          projectedFailure * recovery +
          failureRate * loadPenalty,
      );

      const finalLatency = projectedLatency * (1 + loadPenalty);

      const finalFailureReduction = Math.max(0, failureRate - finalFailureRate);

      const finalLatencyReduction = Math.max(0, latency - finalLatency);

      const score = Math.max(
        0,
        Math.min(
          100,
          Math.round(
            (finalFailureReduction / Math.max(failureRate, 0.01)) * 70 +
              (finalLatencyReduction / Math.max(latency, 1)) * 30 -
              loadPenalty * 25,
          ),
        ),
      );

      const candidate = {
        trafficShift: shift,
        effectiveShift: feasibleShift,
        retryBudget: retry,
        failureRate: finalFailureRate,
        latency: finalLatency,
        score,
      };

      if (
        !bestConfiguration ||
        candidate.score > bestConfiguration.score ||
        (candidate.score === bestConfiguration.score &&
          candidate.failureRate < bestConfiguration.failureRate)
      ) {
        bestConfiguration = candidate;
      }
    }
  }

  return (
    <div className="app">
      {/* =====================================================
          HEADER
      ===================================================== */}

      <header className="topbar">
        <div className="brand">
          <div className="logo">P</div>

          <div>
            <h2>PayLens AI</h2>
            <span>Payment Incident Intelligence</span>
          </div>
        </div>

        {/* RIGHT STATUS */}
        <div className="header-right">
          <div className="header-severity">
            <span className="header-severity-dot"></span>
            <span>{severity.toUpperCase()}</span>
          </div>

          <span className="header-divider">|</span>

          <div className="header-active-badge">ACTIVE</div>
        </div>
      </header>

      <nav className="section-nav" aria-label="Dashboard sections">
        <a href="#overview">Overview</a>
        <a href="#timeline">Timeline</a>
        <a href="#rca">RCA</a>
        <a href="#topology">Topology</a>
        <a href="#impact">Impact</a>
        <a href="#response">Response</a>
        <a href="#simulation">Simulation</a>
        <a href="#validation">Validation</a>
      </nav>

      <main className="container">
        {/* =====================================================
            HERO
        ===================================================== */}

        <section id="overview" className="hero">
          <div className="hero-content">
            <div className="eyebrow">INCIDENT OPERATIONS</div>

            <h1>
              Payment Intelligence
              <br />
              <span>at a glance.</span>
            </h1>

            <p>
              Detect, investigate and understand payment incidents using
              evidence-driven AI.
            </p>

            <div className="hero-meta">
              <span>● Last analysis: current telemetry</span>

              <span>
                ● {incident?.analysis_window_minutes ?? 60} min analysis window
              </span>

              <span>● AI investigation enabled</span>
            </div>
          </div>

          <button
            className="primary-button"
            onClick={analyzeIncident}
            disabled={loading}
          >
            <span>{loading ? "Analyzing..." : "Analyze Incident"}</span>

            {!loading && <span className="button-arrow">→</span>}
          </button>
        </section>

        {/* =====================================================
            ERROR
        ===================================================== */}

        {error && data && (
          <div className="error-banner">
            <span>⚠</span>
            {error}
          </div>
        )}

        {/* =====================================================
            INCIDENT STATUS
        ===================================================== */}

        <section className="status-banner">
          <div className="status-main">
            <div
              className={`status-icon ${
                incidentDetected ? "incident" : "healthy"
              }`}
            >
              {incidentDetected ? "!" : "✓"}
            </div>

            <div>
              <span className="status-label">
                {incidentDetected
                  ? "ACTIVE INCIDENT DETECTED"
                  : "SYSTEM HEALTHY"}
              </span>

              <strong>
                {incidentDetected
                  ? `${severity} severity · ${rootCause}`
                  : "No actionable incident detected"}
              </strong>
            </div>
          </div>

          <div className="status-time">
            <span>TELEMETRY</span>
            <strong>{currentEvents} events</strong>
          </div>
        </section>

        {/* =====================================================
            INCIDENT RISK
        ===================================================== */}

        {incidentDetected && (
          <section className="risk-strip">
            <div className="risk-main">
              <div className="risk-icon">!</div>

              <div>
                <span>INCIDENT RISK</span>

                <strong>
                  {getRiskLevel(
                    failureRate,
                    baselineFailureRate,
                    latency,
                    baselineLatency,
                  )}
                </strong>
              </div>
            </div>

            <div className="risk-progress">
              <div
                style={{
                  width: `${Math.min(
                    calculateRiskScore(
                      failureRate,
                      baselineFailureRate,
                      latency,
                      baselineLatency,
                    ),
                    100,
                  )}%`,
                }}
              ></div>
            </div>

            <div className="risk-stats">
              <span>
                +{(failureRate - baselineFailureRate).toFixed(2)}
                pp failure rate
              </span>

              <span>
                +{Math.round(latency - baselineLatency).toLocaleString()}
                ms latency
              </span>
            </div>
          </section>
        )}

        {/* =====================================================
            KPI METRICS
        ===================================================== */}

        <section className="metrics">
          <MetricCard
            icon="↗"
            title="Failure Rate"
            value={`${failureRate.toFixed(2)}%`}
            subtitle={
              changes?.failure_rate_multiplier
                ? `${changes.failure_rate_multiplier}× baseline`
                : "No baseline comparison"
            }
            detail={`Baseline ${baselineFailureRate.toFixed(2)}%`}
            danger={failureRate > baselineFailureRate}
          />

          <MetricCard
            icon="◷"
            title="Average Latency"
            value={`${Math.round(latency).toLocaleString()} ms`}
            subtitle={
              changes?.latency_multiplier
                ? `${changes.latency_multiplier}× baseline`
                : "No baseline comparison"
            }
            detail={`Baseline ${Math.round(
              baselineLatency,
            ).toLocaleString()} ms`}
            danger={latency > baselineLatency}
          />

          <MetricCard
            icon="!"
            title="Failed Payments"
            value={failedPayments}
            subtitle="Failed transactions"
            detail={`₹${failedValue.toLocaleString()} at risk`}
            danger={failedPayments > 0}
          />

          <MetricCard
            icon="◎"
            title="RCA Confidence"
            value={`${confidence.toFixed(2)}%`}
            subtitle={
              confidence >= 80
                ? "High confidence"
                : confidence >= 60
                  ? "Moderate confidence"
                  : "Low confidence"
            }
            detail={rootCauseCode}
            success={confidence >= 80}
          />
        </section>

        {/* =====================================================
            LIVE TELEMETRY
        ===================================================== */}

        <section className="section live-telemetry-section">
          {liveIncidentStatus === "HEALTHY" && (
            <div className="live-healthy-banner">
              <div>
                <span>LIVE SYSTEM STATUS</span>
                <strong>✓ System healthy</strong>
              </div>

              <span>No actionable incident detected</span>
            </div>
          )}

          <div className="live-telemetry-header">
            <div>
              <div className="eyebrow">LIVE TELEMETRY</div>

              <h2>Payment health in real time</h2>

              <p>
                Continuous telemetry stream feeding the incident detection
                engine.
              </p>
            </div>

            <div
              className={`telemetry-live-status ${
                telemetryLive ? "active" : ""
              }`}
            >
              <span className="telemetry-live-dot"></span>

              <strong>
                {liveIncidentStatus === "INCIDENT_ACTIVE"
                  ? "INCIDENT ACTIVE"
                  : telemetryLive
                    ? "LIVE"
                    : liveIncidentStatus === "DISCONNECTED"
                      ? "OFFLINE"
                      : "CONNECTING"}
              </strong>
            </div>
          </div>

          {/* LIVE METRIC CARDS */}

          <div className="live-telemetry-grid">
            <LiveTelemetryMetric
              label="FAILURE RATE"
              value={`${liveFailureRate.toFixed(2)}%`}
              detail={
                liveFailureRate > baselineFailureRate
                  ? `↑ ${(liveFailureRate - baselineFailureRate).toFixed(
                      2,
                    )} pp vs baseline`
                  : "Within baseline"
              }
              danger={liveFailureRate > baselineFailureRate}
            />

            <LiveTelemetryMetric
              label="AVG LATENCY"
              value={`${Math.round(liveLatency).toLocaleString()} ms`}
              detail={
                liveLatency > baselineLatency
                  ? `↑ ${Math.round(
                      liveLatency - baselineLatency,
                    ).toLocaleString()} ms vs baseline`
                  : "Within baseline"
              }
              danger={liveLatency > baselineLatency}
            />

            <LiveTelemetryMetric
              label="PAYMENT EVENTS"
              value={liveEvents.toLocaleString()}
              detail="Live transaction samples"
            />

            <LiveTelemetryMetric
              label="GATEWAY"
              value={liveGatewayStatus}
              detail={liveGateway}
              danger={
                liveGatewayStatus === "AT RISK" ||
                liveGatewayStatus === "DEGRADED"
              }
            />
          </div>

          {/* FAILURE RATE TREND */}

          <div className="telemetry-trend-card">
            <div className="telemetry-trend-header">
              <div>
                <span>FAILURE RATE TREND</span>

                <strong>{liveFailureRate.toFixed(2)}%</strong>
              </div>

              <div className="trend-live-label">
                <span></span>
                LIVE SAMPLES
              </div>
            </div>

            <div className="telemetry-chart">
              {liveTelemetry.map((sample) => {
                const range = Math.max(trendMax - trendMin, 0.1);

                const normalized =
                  ((sample.failureRate - trendMin) / range) * 100;

                return (
                  <div
                    className="telemetry-bar"
                    key={sample.id}
                    title={`${sample.failureRate.toFixed(2)}% failure rate`}
                  >
                    <div
                      style={{
                        height: `${Math.max(normalized, 8)}%`,
                      }}
                    ></div>
                  </div>
                );
              })}
            </div>

            <div className="telemetry-chart-footer">
              <span>Earlier samples</span>

              <span>Updating every 2 seconds</span>

              <span>Latest</span>
            </div>
          </div>
        </section>

        {/* =====================================================
            INCIDENT TIMELINE
        ===================================================== */}

        <section id="timeline" className="section timeline-section">
          <SectionHeader
            eyebrow="INCIDENT TIMELINE"
            title="From baseline to detection"
            count={`${incident?.analysis_window_minutes ?? 60} min window`}
          />

          <div className="timeline-card">
            <TimelineStep
              number="01"
              label="BASELINE"
              title="Normal operating state"
              value={`${baselineFailureRate.toFixed(2)}% failure rate`}
              detail={`${baselineEvents} baseline payment events`}
              state="normal"
            />

            <TimelineConnector />

            <TimelineStep
              number="02"
              label="ANOMALY"
              title="Payment degradation detected"
              value={`${failureRate.toFixed(2)}% failure rate`}
              detail={
                changes?.failure_rate_multiplier
                  ? `${changes.failure_rate_multiplier}× baseline failure rate`
                  : "Failure rate increased"
              }
              state="warning"
            />

            <TimelineConnector />

            <TimelineStep
              number="03"
              label="CORRELATION"
              title="Multiple telemetry signals aligned"
              value={`${Math.round(latency).toLocaleString()} ms latency`}
              detail={
                changes?.latency_multiplier
                  ? `${changes.latency_multiplier}× baseline latency`
                  : "Latency degradation detected"
              }
              state="warning"
            />

            <TimelineConnector />

            <TimelineStep
              number="04"
              label="RCA"
              title={rootCause}
              value={`${confidence.toFixed(0)}% confidence`}
              detail={rootCauseCode}
              state="primary"
            />
          </div>
        </section>

        {/* =====================================================
            INCIDENT RCA
        ===================================================== */}

        {incidentDetected && (
          <section id="rca" ref={investigationRef} className="incident-card">
            <div className="incident-top">
              <div className="incident-title-area">
                <div className="severity">
                  <span className="severity-dot"></span>
                  {severity} SEVERITY INCIDENT
                </div>

                <h2>{rootCause}</h2>

                <p>
                  {primaryRootCause?.description ||
                    "The payment system is showing abnormal telemetry patterns requiring investigation."}
                </p>

                <div className="root-cause-code">
                  <span>PRIMARY SIGNAL</span>

                  <strong>{rootCauseCode}</strong>
                </div>
              </div>

              <div className="confidence-card">
                <div className="confidence-label">RCA CONFIDENCE</div>

                <div className="confidence-value">{confidence.toFixed(0)}%</div>

                <div className="confidence-track">
                  <div
                    style={{
                      width: `${Math.min(confidence, 100)}%`,
                    }}
                  ></div>
                </div>

                <span>
                  {confidence >= 80
                    ? "High confidence"
                    : confidence >= 60
                      ? "Moderate confidence"
                      : "Low confidence"}
                </span>
              </div>
            </div>

            <div className="incident-command-grid">
              <div className="incident-command-metric">
                <span>FAILURE RATE</span>

                <strong>{failureRate.toFixed(2)}%</strong>

                <small>
                  ↑ {Number(changes?.failure_rate_multiplier ?? 0).toFixed(2)}×
                  baseline
                </small>
              </div>

              <div className="incident-command-metric">
                <span>LATENCY</span>

                <strong>{Math.round(latency).toLocaleString()} ms</strong>

                <small>
                  ↑ {Number(changes?.latency_multiplier ?? 0).toFixed(2)}×
                  baseline
                </small>
              </div>

              <div className="incident-command-metric">
                <span>FAILED PAYMENTS</span>

                <strong>{failedPayments}</strong>

                <small>of {currentEvents} observed</small>
              </div>

              <div className="incident-command-metric">
                <span>FAILED TRANSACTION VALUE</span>

                <strong>₹{failedValue.toLocaleString("en-IN")}</strong>

                <small>value associated with failures</small>
              </div>
            </div>

            <div className="incident-command-context">
              <div>
                <span>GATEWAY</span>
                <strong>
                  {dominantGateway?.key || dominantGateway || "Unknown"}
                </strong>
              </div>

              <div>
                <span>DOMINANT ERROR</span>
                <strong>{dominantErrorCode || "Unknown"}</strong>
              </div>

              <div>
                <span>ANALYSIS WINDOW</span>
                <strong>{incident?.analysis_window_minutes ?? 60} min</strong>
              </div>

              <div>
                <span>STATUS</span>
                <strong>
                  {String(incident?.status || "ACTIVE").toUpperCase()}
                </strong>
              </div>
            </div>

            {/* RCA EXPAND/COLLAPSE */}

            <button
              className="rca-toggle"
              onClick={() => setShowRcaReasoning(!showRcaReasoning)}
            >
              <span>
                {showRcaReasoning ? "Hide RCA reasoning" : "Why this RCA?"}
              </span>

              <span>{showRcaReasoning ? "↑" : "↓"}</span>
            </button>

            {showRcaReasoning && (
              <RcaReasoning
                failureRate={failureRate}
                baselineFailureRate={baselineFailureRate}
                latency={latency}
                baselineLatency={baselineLatency}
                dominantGateway={dominantGateway}
                dominantErrorCode={dominantErrorCode}
                confidence={confidence}
                rootCause={rootCause}
                primaryRootCause={primaryRootCause}
                hypotheses={hypotheses}
              />
            )}

            <div className="explanation-grid">
              <InfoPanel
                icon="01"
                title="What happened?"
                text={
                  ai?.what_happened ||
                  `A ${severity}-severity payment incident was detected during the analyzed window. ${currentEvents} payment events were observed, of which ${failedPayments} failed. The current failure rate was ${failureRate.toFixed(
                    2,
                  )}%.`
                }
              />

              <InfoPanel
                icon="02"
                title="Why did it happen?"
                text={
                  ai?.why_it_happened ||
                  `The strongest evidence supports ${rootCause} with ${confidence.toFixed(
                    2,
                  )}% confidence. The conclusion is based on multiple telemetry signals rather than a single metric.`
                }
              />
            </div>
          </section>
        )}

        <PaymentTopology topology={topology} />

        {/* =====================================================
            AI INVESTIGATION SUMMARY
        ===================================================== */}

        {incidentDetected && (
          <section id="impact" className="investigation-summary">
            <div className="summary-header">
              <div>
                <div className="eyebrow">AI DECISION SUPPORT</div>

                <h2>Investigation Summary</h2>

                <p>A concise operational view of the current incident.</p>
              </div>

              <div className="ai-generated-badge">AI GENERATED</div>
            </div>

            <div className="summary-grid">
              <SummaryItem label="PRIMARY ISSUE" value={rootCause} />

              <SummaryItem
                label="CONFIDENCE"
                value={`${confidence.toFixed(0)}%`}
              />

              <SummaryItem
                label="BUSINESS IMPACT"
                value={`${failedPayments} failed payments`}
              />

              <SummaryItem
                label="VALUE AT RISK"
                value={`₹${failedValue.toLocaleString()}`}
              />
            </div>

            <div className="business-impact-panel">
              <div className="business-impact-header">
                <div>
                  <div className="eyebrow">BUSINESS IMPACT</div>
                  <h3>Financial exposure from this incident</h3>
                  <p>
                    Estimated transaction value affected during the analyzed
                    incident window.
                  </p>
                </div>

                <div className="impact-risk-badge">VALUE AT RISK</div>
              </div>

              <div className="business-impact-grid">
                <div className="business-impact-card primary">
                  <span>TRANSACTION VALUE AT RISK</span>
                  <strong>
                    ₹{transactionValueAtRisk.toLocaleString("en-IN")}
                  </strong>
                  <small>Failed transaction value</small>
                </div>

                <div className="business-impact-card">
                  <span>FAILED PAYMENTS</span>
                  <strong>{failedPayments}</strong>
                  <small>
                    Failed transactions in {analysisWindowMinutes} min
                  </small>
                </div>

                <div className="business-impact-card">
                  <span>VALUE AT RISK / MIN</span>
                  <strong>
                    ₹{Math.round(valueAtRiskPerMinute).toLocaleString("en-IN")}
                  </strong>
                  <small>Average exposure per minute</small>
                </div>

                <div className="business-impact-card">
                  <span>AVG FAILED TRANSACTION</span>
                  <strong>
                    ₹
                    {Math.round(averageFailedTransactionValue).toLocaleString(
                      "en-IN",
                    )}
                  </strong>
                  <small>Average value per failed payment</small>
                </div>
              </div>

              <div className="business-impact-footer">
                <span>RECOVERY POTENTIAL</span>

                <strong>
                  ₹{Math.round(projectedRecoveredValue).toLocaleString("en-IN")}
                </strong>

                <small>
                  Estimated recoverable value ·{" "}
                  {recoveryValuePercent.toFixed(1)}% of value at risk
                </small>
              </div>
            </div>

            <div className="next-action">
              <span>NEXT BEST ACTION</span>

              <strong>
                {recommendations.length > 0
                  ? recommendations[0]
                  : "Inspect gateway and upstream network health metrics for elevated latency and timeout rates."}
              </strong>
            </div>
          </section>
        )}

        {/* =====================================================
            DETECTION SIGNALS
        ===================================================== */}

        {incidentDetected && (
          <section className="section">
            <SectionHeader
              eyebrow="DETECTION ENGINE"
              title="Detection signals"
              count="Evidence contributing to incident"
            />

            <div className="detection-grid">
              <DetectionSignal
                icon="↗"
                label="FAILURE RATE"
                value={`${failureRate.toFixed(2)}%`}
                detail={
                  changes?.failure_rate_multiplier
                    ? `${changes.failure_rate_multiplier}× baseline`
                    : "Elevated"
                }
                level="ELEVATED"
                showBar
                percentage={calculateRelativePercentage(
                  failureRate,
                  baselineFailureRate,
                )}
              />

              <DetectionSignal
                icon="◷"
                label="LATENCY"
                value={`${Math.round(latency).toLocaleString()} ms`}
                detail={
                  changes?.latency_multiplier
                    ? `${changes.latency_multiplier}× baseline`
                    : "Elevated"
                }
                level="ELEVATED"
                showBar
                percentage={calculateRelativePercentage(
                  latency,
                  baselineLatency,
                )}
              />

              <DetectionSignal
                icon="!"
                label="ERROR CODE"
                value={dominantErrorCode}
                detail="Dominant failure signal"
                level="ELEVATED"
              />

              <DetectionSignal
                icon="G"
                label="GATEWAY"
                value={dominantGateway.key}
                detail={`${formatPercent(dominantGateway.value)} failure rate`}
                level="ELEVATED"
              />

              <DetectionSignal
                icon="I"
                label="ISSUER"
                value={dominantIssuer.key}
                detail={`${formatPercent(dominantIssuer.value)} failure rate`}
              />

              <DetectionSignal
                icon="P"
                label="PAYMENT METHOD"
                value={dominantPaymentMethod.key}
                detail={`${formatPercent(
                  dominantPaymentMethod.value,
                )} failure rate`}
              />
            </div>
          </section>
        )}

        {/* =====================================================
            EVIDENCE
        ===================================================== */}

        {evidence.length > 0 && (
          <section className="section">
            <SectionHeader
              eyebrow="INVESTIGATION"
              title="Evidence signals"
              count={`${evidence.length} signals`}
            />

            <div className="evidence-grid">
              {evidence.map((item, index) => (
                <EvidenceCard
                  key={`${item}-${index}`}
                  item={item}
                  index={index}
                />
              ))}
            </div>
          </section>
        )}

        {/* =====================================================
            TELEMETRY BREAKDOWN
        ===================================================== */}

        {incidentDetected && (
          <section className="section">
            <SectionHeader
              eyebrow="TELEMETRY"
              title="Failure distribution"
              count="Current window"
            />

            <div className="breakdown-grid">
              <BreakdownCard title="Gateway" icon="G" data={gatewayRates} />

              <BreakdownCard title="Issuer" icon="I" data={issuerRates} />

              <BreakdownCard
                title="Payment Method"
                icon="P"
                data={paymentMethodRates}
              />
            </div>
          </section>
        )}

        {/* =====================================================
            RESPONSE / RECOMMENDATIONS
        ===================================================== */}

        {incidentDetected && (
          <section id="response" className="response-card">
            <div className="response-header">
              <div>
                <div className="eyebrow">RESPONSE</div>

                <h2>Recommended Actions</h2>

                <p>
                  Advisory actions generated from the incident investigation.
                </p>
              </div>

              <div className="advisory-badge">ADVISORY ONLY</div>
            </div>

            <div className="actions-list">
              {remediationRecommendations.length > 0 ? (
                remediationRecommendations.map((item, index) => (
                  <div className="action-item" key={`${item.action}-${index}`}>
                    <div className="action-number">
                      {String(index + 1).padStart(2, "0")}
                    </div>

                    <div className="action-body">
                      <strong>{item.title}</strong>

                      <span>
                        <b>{item.priority}</b> · {item.description}
                      </span>

                      {Array.isArray(item.decision_basis) &&
                        item.decision_basis.length > 0 && (
                          <div className="action-decision-basis">
                            <div className="action-decision-label">
                              WHY THIS ACTION?
                            </div>

                            <ul>
                              {item.decision_basis.map(
                                (reason, reasonIndex) => (
                                  <li
                                    key={`${item.action}-reason-${reasonIndex}`}
                                  >
                                    {reason}
                                  </li>
                                ),
                              )}
                            </ul>
                          </div>
                        )}
                    </div>

                    <div className="action-arrow">
                      {item.execution === "ADVISORY_ONLY" ? "✓" : "→"}
                    </div>
                  </div>
                ))
              ) : recommendations.length > 0 ? (
                recommendations.map((action, index) => (
                  <div className="action-item" key={`${action}-${index}`}>
                    <div className="action-number">
                      {String(index + 1).padStart(2, "0")}
                    </div>

                    <div className="action-body">
                      <strong>{action}</strong>
                      <span>Recommended mitigation step</span>
                    </div>

                    <div className="action-arrow">→</div>
                  </div>
                ))
              ) : (
                <div className="action-item">
                  <div className="action-number">01</div>

                  <div className="action-body">
                    <strong>Continue monitoring payment health.</strong>
                  </div>
                </div>
              )}
            </div>

            <div className="response-footer">
              <div>
                <span className="footer-icon">✓</span>
                No automatic financial or routing action is executed.
              </div>

              <button
                className="secondary-button"
                onClick={simulateRecovery}
                disabled={recoveryLoading}
              >
                {recoveryLoading ? "Simulating..." : "Simulate Recovery"}

                {!recoveryLoading && <span>→</span>}
              </button>
            </div>
          </section>
        )}

        {/* =====================================================
            RECOVERY SIMULATION
        ===================================================== */}

        {backendSimulation && (
          <section className="recovery-card">
            <div className="recovery-header">
              <div>
                <div className="eyebrow">WHAT-IF ANALYSIS</div>

                <h2>Recovery Simulation</h2>

                <p>Simulated impact of the recommended mitigation strategy.</p>
              </div>

              <div className="recovery-status">
                <span></span>

                {backendSimulation?.recovery_status || "SIMULATION COMPLETE"}
              </div>
            </div>

            <div className="strategy-box">
              <span>SIMULATION STRATEGY</span>

              <strong>
                {backendSimulation?.strategy ||
                  `Simulate traffic redistribution away from ${dominantGateway.key}`}
              </strong>
            </div>

            <div className="action-outcome-box">
              <div>
                <span className="action-outcome-label">ACTION OUTCOME</span>

                <strong>
                  {remediationRecommendations?.[0]?.title ||
                    "Recommended mitigation strategy"}
                </strong>

                <p>What-if impact if the recommended mitigation is applied.</p>
              </div>

              <div className="action-outcome-metrics">
                <div>
                  <span>Failure rate</span>
                  <strong>
                    {Number(
                      backendSimulation?.before?.failure_rate ?? failureRate,
                    ).toFixed(2)}
                    % →{" "}
                    {Number(
                      backendSimulation?.after?.failure_rate ??
                        simulatedFailureRate,
                    ).toFixed(2)}
                    %
                  </strong>
                </div>

                <div>
                  <span>Latency</span>
                  <strong>
                    {Math.round(
                      Number(
                        backendSimulation?.before?.average_latency_ms ??
                          latency,
                      ),
                    ).toLocaleString()}{" "}
                    →{" "}
                    {Math.round(
                      Number(
                        backendSimulation?.after?.average_latency_ms ??
                          simulatedLatency,
                      ),
                    ).toLocaleString()}{" "}
                    ms
                  </strong>
                </div>

                <div>
                  <span>Estimated recovered</span>
                  <strong>
                    {backendSimulation?.improvement
                      ?.estimated_recovered_transactions ??
                      estimatedRecovered}{" "}
                    txns
                  </strong>
                </div>
              </div>
            </div>

            <div className="before-after">
              <div className="recovery-side before">
                <span className="side-label">BEFORE MITIGATION</span>

                <div className="recovery-value">
                  {Number(
                    backendSimulation?.before?.failure_rate ?? failureRate,
                  ).toFixed(2)}
                  %
                </div>

                <span>Failure rate</span>

                <div className="recovery-latency">
                  <strong>
                    {Math.round(
                      Number(
                        backendSimulation?.before?.average_latency_ms ??
                          latency,
                      ),
                    ).toLocaleString()}
                  </strong>

                  <span>ms latency</span>
                </div>
              </div>

              <div className="recovery-arrow-large">→</div>

              <div className="recovery-side after">
                <span className="side-label">AFTER SIMULATED MITIGATION</span>

                <div className="recovery-value">
                  {Number(
                    backendSimulation?.after?.failure_rate ??
                      simulatedFailureRate,
                  ).toFixed(2)}
                  %
                </div>

                <span>Failure rate</span>

                <div className="recovery-latency">
                  <strong>
                    {Math.round(
                      Number(
                        backendSimulation?.after?.average_latency_ms ??
                          simulatedLatency,
                      ),
                    ).toLocaleString()}
                  </strong>

                  <span>ms latency</span>
                </div>
              </div>
            </div>

            <div className="improvement-grid">
              <ImprovementCard
                label="Failure-rate reduction"
                value={`↓ ${
                  backendSimulation?.improvement
                    ?.failure_rate_reduction_percent ?? failureReduction
                }%`}
              />

              <ImprovementCard
                label="Latency reduction"
                value={`↓ ${Math.round(
                  backendSimulation?.improvement?.latency_reduction_ms ??
                    latencyReduction,
                ).toLocaleString()} ms`}
              />

              <ImprovementCard
                label="Recovery score"
                value={`${backendSimulation?.recovery_score ?? "—"}%`}
              />

              <ImprovementCard
                label="Estimated recovered"
                value={`${
                  backendSimulation?.improvement
                    ?.estimated_recovered_transactions ?? estimatedRecovered
                } txns`}
              />

              <ImprovementCard
                label="Recovered transaction value"
                value={`₹${Number(
                  backendSimulation?.improvement
                    ?.estimated_recovered_transaction_value ?? 0,
                ).toLocaleString()}`}
              />
            </div>

            <div className="simulation-note">
              <span>⚠</span>

              <div>
                <strong>Simulation only</strong>

                <p>
                  No real payment-routing action was executed. Actual recovery
                  depends on gateway, issuer, network and merchant
                  configuration.
                </p>
              </div>
            </div>
          </section>
        )}

        {/* =====================================================
            MODEL VALIDATION
        ===================================================== */}

        <section id="validation" className="section evaluation-section">
          <SectionHeader
            eyebrow="MODEL VALIDATION"
            title="AI System Evaluation"
            count={
              evaluation
                ? `${evaluation.scenarios_tested} scenarios tested`
                : "5 controlled scenarios"
            }
          />

          <div className="model-validation-card">
            <div className="model-validation-intro">
              <div>
                <span className="evaluation-kicker">END-TO-END VALIDATION</span>
                <h3>Validate incident detection and root-cause reasoning</h3>
                <p>
                  Runs the same detection and RCA engines against isolated,
                  deterministic telemetry scenarios.
                </p>
              </div>

              <button
                className="primary-button evaluation-run-button"
                onClick={runEvaluation}
                disabled={evaluationLoading}
              >
                {evaluationLoading ? "Running evaluation..." : "Run Evaluation"}
                {!evaluationLoading && <span className="button-arrow">→</span>}
              </button>
            </div>

            {evaluationError && (
              <div className="evaluation-error">
                <span>⚠</span>
                {evaluationError}
              </div>
            )}

            {evaluation && (
              <>
                <div className="evaluation-summary-grid">
                  <EvaluationMetric
                    label="Detection Accuracy"
                    value={`${evaluation.detection_accuracy_percent}%`}
                    detail="Correct incident detection"
                    positive={evaluation.detection_accuracy_percent === 100}
                  />
                  <EvaluationMetric
                    label="RCA Accuracy"
                    value={`${evaluation.rca_accuracy_percent}%`}
                    detail="Correct root-cause classification"
                    positive={evaluation.rca_accuracy_percent === 100}
                  />
                  <EvaluationMetric
                    label="False Positives"
                    value={evaluation.false_positives}
                    detail="Healthy systems incorrectly flagged"
                    positive={evaluation.false_positives === 0}
                  />
                  <EvaluationMetric
                    label="False Negatives"
                    value={evaluation.false_negatives}
                    detail="Incidents missed by detector"
                    positive={evaluation.false_negatives === 0}
                  />
                </div>

                <div
                  className={`evaluation-status ${evaluation.status === "passed" ? "passed" : "review"}`}
                >
                  <span>{evaluation.status === "passed" ? "✓" : "!"}</span>
                  <div>
                    <strong>
                      {evaluation.status === "passed"
                        ? "Evaluation Passed"
                        : "Evaluation Needs Review"}
                    </strong>
                    <p>
                      {evaluation.scenarios_tested} deterministic scenarios
                      completed.
                    </p>
                  </div>
                </div>

                <div className="evaluation-table-wrap">
                  <div className="evaluation-table-head">
                    <span>SCENARIO</span>
                    <span>DETECTION</span>
                    <span>RCA</span>
                    <span>CONFIDENCE</span>
                  </div>

                  {evaluation.results?.map((result) => (
                    <div className="evaluation-table-row" key={result.scenario}>
                      <div className="evaluation-scenario">
                        <span
                          className={
                            result.detection_correct && result.rca_correct
                              ? "scenario-pass"
                              : "scenario-fail"
                          }
                        >
                          {result.detection_correct && result.rca_correct
                            ? "✓"
                            : "!"}
                        </span>
                        <strong>{formatScenarioName(result.scenario)}</strong>
                      </div>
                      <span
                        className={
                          result.detection_correct
                            ? "result-pass"
                            : "result-fail"
                        }
                      >
                        {result.detection_correct ? "PASS" : "FAIL"}
                      </span>
                      <span
                        className={
                          result.rca_correct ? "result-pass" : "result-fail"
                        }
                      >
                        {result.expected_root_cause === null
                          ? "N/A"
                          : result.rca_correct
                            ? "PASS"
                            : "FAIL"}
                      </span>
                      <span className="evaluation-confidence">
                        {result.expected_root_cause === null
                          ? "—"
                          : `${Number(result.confidence ?? 0).toFixed(1)}%`}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {!evaluation && !evaluationLoading && !evaluationError && (
              <div className="evaluation-empty">
                <span>◎</span>
                <div>
                  <strong>Evaluation not run yet</strong>
                  <p>
                    Click “Run Evaluation” to validate all five controlled
                    scenarios.
                  </p>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* =====================================================
    INCIDENT HISTORY
===================================================== */}

        <section className="section incident-history-section">
          <SectionHeader
            eyebrow="INCIDENT HISTORY"
            title="Previous payment incidents"
            count={`${incidentHistory.length} incidents`}
          />

          <div className="incident-history-card">
            {historyLoading ? (
              <div className="history-empty">
                <span className="history-loading-dot"></span>
                <div>
                  <strong>Loading incident history...</strong>
                  <p>Fetching previously detected incidents.</p>
                </div>
              </div>
            ) : incidentHistory.length === 0 ? (
              <div className="history-empty">
                <span>✓</span>
                <div>
                  <strong>No incidents recorded</strong>
                  <p>PayLens has not persisted any incidents yet.</p>
                </div>
              </div>
            ) : (
              <div className="history-list">
                {incidentHistory.map((item) => {
                  const detectedAt = item.detected_at
                    ? new Date(item.detected_at)
                    : null;

                  const severityClass = String(
                    item.severity || "UNKNOWN",
                  ).toLowerCase();

                  const statusClass = String(
                    item.status || "UNKNOWN",
                  ).toLowerCase();

                  return (
                    <div className="history-item" key={item.id}>
                      <div className="history-number">#{item.id}</div>

                      <div className="history-main">
                        <div className="history-title-row">
                          <div>
                            <span className="history-label">ROOT CAUSE</span>

                            <h3>
                              {item.root_cause_title ||
                                item.root_cause ||
                                "Unknown incident"}
                            </h3>
                          </div>

                          <div className="history-badges">
                            <span
                              className={`history-severity ${severityClass}`}
                            >
                              {item.severity || "UNKNOWN"}
                            </span>

                            <span
                              className={`history-status ${
                                String(item.status || "").toLowerCase() ===
                                "active"
                                  ? "active"
                                  : "resolved"
                              }`}
                            >
                              {item.status || "UNKNOWN"}
                            </span>
                          </div>
                        </div>

                        <div className="history-meta">
                          <div>
                            <span>GATEWAY</span>
                            <strong>{item.gateway || "—"}</strong>
                          </div>

                          <div>
                            <span>FAILURE RATE</span>
                            <strong>
                              {Number(item.failure_rate ?? 0).toFixed(2)}%
                            </strong>
                          </div>

                          <div>
                            <span>BASELINE</span>
                            <strong>
                              {Number(item.baseline_failure_rate ?? 0).toFixed(
                                2,
                              )}
                              %
                            </strong>
                          </div>

                          <div>
                            <span>FAILED PAYMENTS</span>
                            <strong>
                              {Number(item.failed_events ?? 0).toLocaleString()}
                            </strong>
                          </div>

                          <div>
                            <span>VALUE AT RISK</span>
                            <strong>
                              ₹
                              {Number(
                                item.failed_transaction_value ?? 0,
                              ).toLocaleString()}
                            </strong>
                          </div>

                          <div>
                            <span>RCA CONFIDENCE</span>
                            <strong>
                              {Number(item.confidence ?? 0).toFixed(1)}%
                            </strong>
                          </div>
                        </div>

                        <div className="history-footer">
                          <span>
                            {detectedAt
                              ? detectedAt.toLocaleString("en-IN", {
                                  day: "2-digit",
                                  month: "short",
                                  year: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })
                              : "Unknown detection time"}
                          </span>

                          <span>
                            Latency:{" "}
                            {Math.round(
                              Number(item.average_latency_ms ?? 0),
                            ).toLocaleString()}{" "}
                            ms
                          </span>

                          {item.resolved_at && (
                            <span>
                              Resolved:{" "}
                              {new Date(item.resolved_at).toLocaleString()}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="history-confidence">
                        <span>CONFIDENCE</span>
                        <strong>
                          {Number(item.confidence ?? 0).toFixed(0)}%
                        </strong>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        {/* =====================================================
            DECISION SIMULATOR
        ===================================================== */}

        {incidentDetected && (
          <section id="simulation" className="section simulator-section">
            <SectionHeader
              eyebrow="DECISION SIMULATOR"
              title="What if traffic is redistributed?"
              count="Interactive projection"
            />

            <div className="simulator-card">
              <div className="simulator-top">
                <div>
                  <span className="simulator-label">
                    TRAFFIC REDISTRIBUTION
                  </span>

                  <h3>
                    Simulate traffic shift away from {dominantGateway.key}
                  </h3>
                </div>

                <div className="simulator-score">{trafficShift}%</div>
              </div>

              <div className="slider-box">
                <div className="slider-labels">
                  <span>0% shift</span>
                  <span>100% shift</span>
                </div>

                <input
                  type="range"
                  min="0"
                  max="100"
                  value={trafficShift}
                  onChange={(event) =>
                    setTrafficShift(Number(event.target.value))
                  }
                />

                <div className="slider-caption">
                  {trafficShift}% of affected traffic shifted
                </div>
              </div>

              <div className="slider-box">
                <div className="slider-labels">
                  <span>Failover capacity</span>
                  <strong>{failoverCapacity}%</strong>
                </div>

                <input
                  type="range"
                  min="20"
                  max="100"
                  step="5"
                  value={failoverCapacity}
                  onChange={(event) =>
                    setFailoverCapacity(Number(event.target.value))
                  }
                />

                <div className="slider-caption">
                  Alternate gateway can absorb up to {failoverCapacity}% of
                  shifted traffic
                </div>
              </div>

              <div className="slider-box">
                <div className="slider-labels">
                  <span>Retry budget</span>
                  <strong>{retryBudget}%</strong>
                </div>

                <input
                  type="range"
                  min="0"
                  max="30"
                  step="5"
                  value={retryBudget}
                  onChange={(event) =>
                    setRetryBudget(Number(event.target.value))
                  }
                />

                <div className="slider-caption">
                  Up to {retryBudget}% additional retry attempts allowed
                </div>
              </div>

              {capacityLimited && (
                <div className="capacity-warning">
                  <span>⚠</span>
                  <div>
                    <strong>Failover capacity constrained</strong>
                    <p>
                      Requested shift of {trafficShift}% exceeds the modeled
                      failover capacity of {failoverCapacity}%. Projection is
                      capped at {effectiveShift}%.
                    </p>
                  </div>
                </div>
              )}

              <div className="projection-card">
                <div className="projection-side">
                  <span>CURRENT</span>

                  <strong>{failureRate.toFixed(2)}%</strong>

                  <small>
                    {Math.round(latency).toLocaleString()} ms latency
                  </small>
                </div>

                <div className="projection-arrow">→</div>

                <div className="projection-side projected">
                  <span>PROJECTED</span>

                  <strong>{retryAdjustedFailureRate.toFixed(2)}%</strong>

                  <small>
                    {Math.round(retryAdjustedLatency).toLocaleString()} ms
                    latency
                  </small>
                </div>
              </div>

              <div className="projection-metrics">
                <ProjectionMetric
                  label="Failure-rate reduction"
                  value={`↓ ${failureReduction.toFixed(2)} pp`}
                />

                <ProjectionMetric
                  label="Latency reduction"
                  value={`↓ ${Math.round(
                    latencyReduction,
                  ).toLocaleString()} ms`}
                />

                <ProjectionMetric
                  label="Estimated recovered"
                  value={`+${estimatedRecovered} txns`}
                />

                <ProjectionMetric
                  label="Retry recovered"
                  value={`+${retryRecoveredTransactions} txns`}
                />

                <ProjectionMetric
                  label="Retry load impact"
                  value={`+${(retryLoadPenalty * 100).toFixed(1)}%`}
                />

                <div className="simulation-decision">
                  <div>
                    <span>SIMULATION OUTCOME</span>
                    <strong>{decisionOutcome}</strong>
                  </div>

                  <div className="simulation-score-value">
                    <span>RECOVERY SCORE</span>
                    <strong>{recoveryScore}/100</strong>
                  </div>
                </div>
              </div>

              <div className="best-configuration">
                <div className="best-configuration-header">
                  <div>
                    <span>RECOMMENDED CONFIGURATION</span>
                    <strong>Best feasible mitigation</strong>
                  </div>

                  <div className="best-configuration-score">
                    {bestConfiguration?.score ?? 0}/100
                  </div>
                </div>

                <div className="best-configuration-grid">
                  <div>
                    <span>TRAFFIC SHIFT</span>
                    <strong>{bestConfiguration?.trafficShift ?? 0}%</strong>
                  </div>

                  <div>
                    <span>FAILOVER CAPACITY</span>
                    <strong>{failoverCapacity}%</strong>
                  </div>

                  <div>
                    <span>RETRY BUDGET</span>
                    <strong>{bestConfiguration?.retryBudget ?? 0}%</strong>
                  </div>

                  <div>
                    <span>PROJECTED FAILURE</span>
                    <strong>
                      {Number(
                        bestConfiguration?.failureRate ?? failureRate,
                      ).toFixed(2)}
                      %
                    </strong>
                  </div>

                  <div>
                    <span>PROJECTED LATENCY</span>
                    <strong>
                      {Math.round(
                        bestConfiguration?.latency ?? latency,
                      ).toLocaleString()}{" "}
                      ms
                    </strong>
                  </div>
                </div>

                <p>
                  Recommendation is optimized against failure reduction, latency
                  improvement and retry overhead while respecting the modeled
                  failover capacity.
                </p>
              </div>

              <div className="recovery-verification-action">
                <div>
                  <span>POST-MITIGATION VERIFICATION</span>
                  <strong>
                    Verify recovery against live payment telemetry
                  </strong>

                  <p>
                    PayLens will observe live failure rate and latency for 15
                    seconds to determine whether recovery is actually visible in
                    telemetry.
                  </p>
                </div>

                <button
                  className="secondary-button"
                  onClick={verifyRecovery}
                  disabled={recoveryLoading}
                >
                  {recoveryLoading ? "Verifying..." : "Verify Recovery"}

                  {!recoveryLoading && <span>→</span>}
                </button>
              </div>

              <div className="simulation-disclaimer">
                <span>ⓘ</span>

                <span>
                  Interactive projection based on payment telemetry. No real
                  payment-routing action is executed.
                </span>
              </div>

              <div className="recovery-verification-card">
                <div className="recovery-verification-header">
                  <div>
                    <span>RECOVERY VERIFICATION</span>
                    <h3>
                      {recoveryVerification.status === "NOT_VERIFIED"
                        ? "Recovery not yet verified"
                        : recoveryVerification.status === "VERIFYING"
                          ? "Recovery verification in progress"
                          : recoveryVerification.status === "RECOVERY_VERIFIED"
                            ? "Recovery verified"
                            : "Recovery verification failed"}
                    </h3>
                  </div>

                  <div
                    className={`verification-status verification-${String(
                      recoveryVerification.status,
                    ).toLowerCase()}`}
                  >
                    {recoveryVerification.status === "NOT_VERIFIED"
                      ? "NOT VERIFIED"
                      : recoveryVerification.status === "VERIFYING"
                        ? "VERIFYING"
                        : recoveryVerification.status === "RECOVERY_VERIFIED"
                          ? "VERIFIED"
                          : "FAILED"}
                  </div>
                </div>

                {recoveryVerification.status === "NOT_VERIFIED" && (
                  <p className="verification-message">
                    No post-mitigation telemetry has been observed yet. Start
                    verification after applying a mitigation.
                  </p>
                )}

                {recoveryVerification.status === "VERIFYING" && (
                  <p className="verification-message">
                    Observing live payment telemetry. Verification will complete
                    after the 15-second observation window.
                  </p>
                )}

                {recoveryVerification.result && (
                  <div className="verification-metrics">
                    <div>
                      <span>OBSERVED FAILURE RATE</span>
                      <strong>
                        {Number(
                          recoveryVerification.result.observedFailureRate ?? 0,
                        ).toFixed(2)}
                        %
                      </strong>
                      <small>
                        {recoveryVerification.result.failureRecovered
                          ? "Improved"
                          : "No improvement observed"}
                      </small>
                    </div>

                    <div>
                      <span>OBSERVED LATENCY</span>
                      <strong>
                        {Math.round(
                          recoveryVerification.result.observedLatency ?? 0,
                        ).toLocaleString()}
                        ms
                      </strong>
                      <small>
                        {recoveryVerification.result.latencyRecovered
                          ? "Improved"
                          : "No improvement observed"}
                      </small>
                    </div>

                    <div>
                      <span>FAILURE IMPROVEMENT</span>
                      <strong>
                        {Number(
                          recoveryVerification.result.failureImprovement ?? 0,
                        ).toFixed(1)}
                        %
                      </strong>
                    </div>

                    <div>
                      <span>LATENCY IMPROVEMENT</span>
                      <strong>
                        {Number(
                          recoveryVerification.result.latencyImprovement ?? 0,
                        ).toFixed(1)}
                        %
                      </strong>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}

        {/* =====================================================
            RCA HYPOTHESES
        ===================================================== */}

        {hypotheses.length > 0 && (
          <section className="section">
            <SectionHeader
              eyebrow="ROOT CAUSE ANALYSIS"
              title="Investigation hypotheses"
              count={`${hypotheses.length} hypotheses`}
            />

            <div className="hypothesis-grid">
              {hypotheses.map((hypothesis, index) => (
                <div
                  className="hypothesis-card"
                  key={`${hypothesis.title}-${index}`}
                >
                  <div className="hypothesis-rank">#{index + 1}</div>

                  <div className="hypothesis-main">
                    <div className="hypothesis-header">
                      <div>
                        <span className="hypothesis-type">
                          {index === 0
                            ? "PRIMARY HYPOTHESIS"
                            : "SECONDARY HYPOTHESIS"}
                        </span>

                        <h3>{hypothesis.title}</h3>
                      </div>

                      <div className="score-circle">
                        <strong>
                          {Number(hypothesis.score ?? 0).toFixed(0)}
                        </strong>

                        <span>SCORE</span>
                      </div>
                    </div>

                    <div className="hypothesis-bar">
                      <div
                        style={{
                          width: `${Math.min(
                            (Number(hypothesis.score ?? 0) / 110) * 100,
                            100,
                          )}%`,
                        }}
                      ></div>
                    </div>

                    <div className="hypothesis-evidence-list">
                      {Array.isArray(hypothesis.evidence) &&
                        hypothesis.evidence.map((item, evidenceIndex) => (
                          <div
                            className="hypothesis-evidence"
                            key={evidenceIndex}
                          >
                            <span
                              className={`strength ${String(
                                item?.strength || "",
                              )
                                .toLowerCase()
                                .replace("_", "-")}`}
                            >
                              {item?.strength || "SIGNAL"}
                            </span>

                            <p>
                              {item?.explanation ||
                                "Supporting telemetry evidence."}
                            </p>
                          </div>
                        ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* =====================================================
            DATA FOOTER
        ===================================================== */}

        <section className="data-info">
          <div>
            <span>ANALYSIS WINDOW</span>

            <strong>{incident?.analysis_window_minutes ?? 60} min</strong>
          </div>

          <div>
            <span>BASELINE EVENTS</span>

            <strong>{baselineEvents}</strong>
          </div>

          <div>
            <span>CURRENT EVENTS</span>

            <strong>{currentEvents}</strong>
          </div>

          <div>
            <span>STATUS</span>

            <strong>{incidentDetected ? "Incident detected" : "Normal"}</strong>
          </div>
        </section>
      </main>
    </div>
  );
}

/* =========================================================
   COMPONENTS
========================================================= */

function MetricCard({ icon, title, value, subtitle, detail, danger, success }) {
  return (
    <div className="metric-card">
      <div className="metric-top">
        <div className="metric-icon">{icon}</div>

        <span className="metric-title">{title}</span>
      </div>

      <strong className="metric-value">{value}</strong>

      <div className="metric-bottom">
        <span
          className={
            danger
              ? "metric-subtitle danger"
              : success
                ? "metric-subtitle success"
                : "metric-subtitle"
          }
        >
          {danger ? "↑ " : ""}
          {subtitle}
        </span>

        <span className="metric-detail">{detail}</span>
      </div>
    </div>
  );
}

function LiveTelemetryMetric({ label, value, detail, danger = false }) {
  return (
    <div className="live-telemetry-metric">
      <div className="live-metric-label">{label}</div>

      <strong
        className={danger ? "live-metric-value danger" : "live-metric-value"}
      >
        {value}
      </strong>

      <span
        className={danger ? "live-metric-detail danger" : "live-metric-detail"}
      >
        {detail}
      </span>
    </div>
  );
}

function InfoPanel({ icon, title, text }) {
  return (
    <div className="dark-panel">
      <div className="panel-icon">{icon}</div>

      <div>
        <h3>{title}</h3>

        <p>{text}</p>
      </div>
    </div>
  );
}

function SectionHeader({ eyebrow, title, count }) {
  return (
    <div className="section-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>

        <h2>{title}</h2>
      </div>

      {count && <span className="section-count">{count}</span>}
    </div>
  );
}

function TimelineStep({ number, label, title, value, detail, state }) {
  return (
    <div className="timeline-step">
      <div className={`timeline-number ${state}`}>{number}</div>

      <div className="timeline-label">{label}</div>

      <h3>{title}</h3>

      <strong>{value}</strong>

      <span>{detail}</span>
    </div>
  );
}

function TimelineConnector() {
  return (
    <div className="timeline-connector">
      <span></span>
    </div>
  );
}

function PaymentTopology({ topology }) {
  if (!topology) {
    return null;
  }

  const dominantPath = topology.dominant_path;

  const methodGateway = topology.relationships?.payment_method_gateway ?? [];

  const gatewayIssuer = topology.relationships?.gateway_issuer ?? [];

  const fullPaths = topology.relationships?.full_payment_paths ?? [];

  const affectedMethods = methodGateway
    .filter((item) => item.failed_events > 0)
    .sort((a, b) => b.failed_events - a.failed_events);

  const affectedGatewayIssuers = gatewayIssuer
    .filter((item) => item.failed_events > 0)
    .sort((a, b) => b.failed_events - a.failed_events);

  const affectedPaths = fullPaths
    .slice()
    .sort((a, b) => b.failed_events - a.failed_events)
    .slice(0, 5);

  const isDominantMethod = (item) =>
    dominantPath &&
    item.payment_method === dominantPath.payment_method &&
    item.gateway === dominantPath.gateway;

  const isDominantGatewayIssuer = (item) =>
    dominantPath &&
    item.gateway === dominantPath.gateway &&
    item.issuer === dominantPath.issuer;

  return (
    <section id="topology" className="payment-topology">
      {/* HEADER */}
      <div className="topology-header">
        <div>
          <div className="section-kicker">PAYMENT TOPOLOGY</div>

          <h3>Observed Payment Dependency Graph</h3>

          <p>
            Event-backed dependency paths identified from the active incident
            window.
          </p>
        </div>

        <div className="topology-window">
          <span className="topology-live-dot" />
          Last {topology.window_minutes} min
        </div>
      </div>

      {/* DOMINANT PATH */}
      {dominantPath && (
        <div className="topology-dominant">
          <div className="topology-dominant-top">
            <div>
              <div className="dominant-path-label">
                DOMINANT OBSERVED FAILURE PATH
              </div>

              <div className="dominant-path">
                <div className="topology-node active">
                  <span className="node-type">METHOD</span>
                  <strong>{dominantPath.payment_method}</strong>
                </div>

                <span className="topology-connector active">→</span>

                <div className="topology-node critical">
                  <span className="node-type">GATEWAY</span>
                  <strong>{dominantPath.gateway}</strong>
                </div>

                <span className="topology-connector active">→</span>

                <div className="topology-node active">
                  <span className="node-type">ISSUER</span>
                  <strong>{dominantPath.issuer}</strong>
                </div>

                <span className="topology-connector critical">→</span>

                <div className="topology-node error">
                  <span className="node-type">FAILURE</span>
                  <strong>{dominantPath.error}</strong>
                </div>
              </div>
            </div>

            <div className="dominant-risk-badge">
              <span>FAILURE RATE</span>
              <strong>{dominantPath.failure_rate}%</strong>
            </div>
          </div>

          <div className="dominant-path-stats">
            <div>
              <span>Failed events</span>
              <strong>{dominantPath.failed_events}</strong>
            </div>

            <div>
              <span>Observed events</span>
              <strong>{dominantPath.events}</strong>
            </div>

            <div>
              <span>Path status</span>
              <strong className="critical-text">CRITICAL</strong>
            </div>
          </div>
        </div>
      )}

      {/* GRAPH */}
      <div className="topology-graph">
        {/* COLUMN 1 */}
        <div className="topology-column">
          <div className="topology-column-header">
            <span className="column-index">01</span>

            <div>
              <strong>Payment Method</strong>
              <small>Traffic entry point</small>
            </div>
          </div>

          <div className="topology-nodes">
            {affectedMethods.map((item) => (
              <div
                className={`graph-node ${
                  isDominantMethod(item) ? "dominant-node" : ""
                }`}
                key={`${item.payment_method}-${item.gateway}`}
              >
                <div className="graph-node-main">
                  <div className="node-icon">
                    {item.payment_method?.charAt(0)?.toUpperCase()}
                  </div>

                  <div>
                    <strong>{item.payment_method}</strong>

                    <span>→ {item.gateway}</span>
                  </div>
                </div>

                <div className="graph-node-metric">
                  <strong>{item.failure_rate}%</strong>

                  <small>{item.failed_events} failed</small>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* CONNECTOR */}
        <div className="graph-flow">
          <div className="flow-line" />
          <span>routes to</span>
          <div className="flow-line" />
        </div>

        {/* COLUMN 2 */}
        <div className="topology-column">
          <div className="topology-column-header">
            <span className="column-index">02</span>

            <div>
              <strong>Gateway</strong>
              <small>Routing layer</small>
            </div>
          </div>

          <div className="topology-nodes">
            {affectedGatewayIssuers.map((item) => (
              <div
                className={`graph-node ${
                  isDominantGatewayIssuer(item) ? "critical-node" : ""
                }`}
                key={`${item.gateway}-${item.issuer}`}
              >
                <div className="graph-node-main">
                  <div className="node-icon gateway">G</div>

                  <div>
                    <strong>{item.gateway}</strong>

                    <span>→ {item.issuer}</span>
                  </div>
                </div>

                <div className="graph-node-metric">
                  <strong>{item.failure_rate}%</strong>

                  <small>{item.failed_events} failed</small>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* CONNECTOR */}
        <div className="graph-flow">
          <div className="flow-line" />
          <span>depends on</span>
          <div className="flow-line" />
        </div>

        {/* COLUMN 3 */}
        <div className="topology-column">
          <div className="topology-column-header">
            <span className="column-index">03</span>

            <div>
              <strong>Failure Paths</strong>
              <small>Observed incident signals</small>
            </div>
          </div>

          <div className="topology-nodes">
            {affectedPaths.map((item) => (
              <div
                className="graph-node failure-node"
                key={[
                  item.payment_method,
                  item.gateway,
                  item.issuer,
                  item.error,
                ].join("-")}
              >
                <div className="failure-path-line">
                  <span>{item.payment_method}</span>

                  <i>→</i>

                  <span>{item.gateway}</span>

                  <i>→</i>

                  <span>{item.issuer}</span>
                </div>

                <div className="failure-error">
                  <span className="failure-dot" />

                  {item.error}
                </div>

                <div className="failure-bottom">
                  <span>{item.failed_events} failed events</span>

                  <strong>{item.failure_rate}%</strong>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* GRAPH FOOTER */}
      <div className="topology-footer">
        <div className="topology-legend">
          <span>
            <i className="legend-dot normal" />
            Observed dependency
          </span>

          <span>
            <i className="legend-dot affected" />
            Affected dependency
          </span>

          <span>
            <i className="legend-dot critical" />
            Critical failure path
          </span>
        </div>

        <div className="topology-footnote">
          Relationships are derived from observed payment events, not inferred
          aggregates.
        </div>
      </div>
    </section>
  );
}
function RcaReasoning({
  failureRate,
  baselineFailureRate,
  latency,
  baselineLatency,
  dominantGateway,
  dominantErrorCode,
  confidence,
  rootCause,
  primaryRootCause,
  hypotheses,
}) {
  const evidence = Array.isArray(primaryRootCause?.evidence)
    ? primaryRootCause.evidence
    : [];

  const evidenceTotal =
    evidence.length > 0
      ? evidence.reduce((total, item) => total + Number(item?.score ?? 0), 0)
      : Number(primaryRootCause?.score ?? 0);

  const selectedConfidence = Number(
    primaryRootCause?.confidence ?? confidence ?? 0,
  );

  const formatSignalName = (value) =>
    String(value || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());

  const getEvidenceValue = (item) => {
    const signal = String(item?.signal || "").toLowerCase();

    if (signal === "gateway_error") {
      return dominantErrorCode || "GATEWAY_TIMEOUT";
    }

    if (signal === "failure_rate") {
      return `${failureRate.toFixed(2)}%`;
    }

    if (signal === "latency") {
      return `${Math.round(latency).toLocaleString()} ms`;
    }

    if (signal === "gateway_failure_rate") {
      return `${Number(
        primaryRootCause?.gateway_failure_rate ?? failureRate,
      ).toFixed(2)}%`;
    }

    if (signal === "gateway_isolation") {
      return dominantGateway?.key || dominantGateway || "gateway_b";
    }

    return formatSignalName(item?.signal);
  };

  const alternativeHypotheses = Array.isArray(
    primaryRootCause?.alternative_hypotheses,
  )
    ? primaryRootCause.alternative_hypotheses
    : Array.isArray(hypotheses)
      ? hypotheses
          .filter((item) => item?.cause !== primaryRootCause?.cause)
          .sort((a, b) => Number(b?.score ?? 0) - Number(a?.score ?? 0))
      : [];

  const decisionMargin = Number(primaryRootCause?.score_margin ?? 0);

  return (
    <div className="rca-reasoning">
      {/* =====================================================
          HEADER
      ===================================================== */}

      <div className="rca-reasoning-header">
        <div>
          <span className="rca-mini-label">ROOT CAUSE DECISION TRACE</span>

          <h3>Why {primaryRootCause?.title || rootCause}?</h3>

          <p>
            PayLens selected the primary cause by combining independent
            telemetry signals and comparing competing hypotheses.
          </p>
        </div>

        <div className="rca-confidence-block">
          <span>CONFIDENCE</span>

          <strong>{selectedConfidence.toFixed(0)}%</strong>

          <small>HIGH CONFIDENCE</small>
        </div>
      </div>

      {/* =====================================================
          DECISION SUMMARY
      ===================================================== */}

      <div className="rca-decision-summary">
        <div className="rca-decision-main">
          <div className="rca-decision-icon">✓</div>

          <div>
            <span className="rca-decision-label">PRIMARY ROOT CAUSE</span>

            <strong>{primaryRootCause?.title || rootCause}</strong>

            <p>
              Multiple independent signals converge on the same failure domain.
            </p>
          </div>
        </div>

        <div className="rca-score-total">
          <span>EVIDENCE SCORE</span>

          <strong>+{evidenceTotal}</strong>

          <small>combined signal weight</small>

          {alternativeHypotheses.length > 0 && (
            <small className="rca-decision-margin">
              +{decisionMargin} lead over next hypothesis
            </small>
          )}
        </div>
      </div>

      {/* =====================================================
          EVIDENCE
      ===================================================== */}

      <div className="rca-section-heading">
        <div>
          <span className="rca-mini-label">SUPPORTING EVIDENCE</span>

          <h4>Signals supporting the decision</h4>
        </div>

        <span className="rca-evidence-count">
          {evidence.length > 0 ? evidence.length : 4} signals
        </span>
      </div>

      <div className="rca-signal-grid">
        {evidence.length > 0 ? (
          evidence.map((item, index) => (
            <div className="rca-signal" key={`${item.signal}-${index}`}>
              <div className="rca-signal-top">
                <span>{formatSignalName(item.signal)}</span>

                <strong>{formatSignalName(item.strength)}</strong>
              </div>

              <h4>{getEvidenceValue(item)}</h4>

              <p>{item.explanation || "Supporting telemetry evidence."}</p>

              <div className="rca-evidence-score">
                <span>Evidence weight</span>

                <strong>+{Number(item.score ?? 0)}</strong>
              </div>
            </div>
          ))
        ) : (
          <>
            <RcaSignal
              label="Failure rate"
              value={`${failureRate.toFixed(2)}%`}
              detail={`${(
                failureRate / Math.max(baselineFailureRate, 0.01)
              ).toFixed(2)}× above baseline`}
              strength="Strong"
            />

            <RcaSignal
              label="Latency"
              value={`${Math.round(latency).toLocaleString()} ms`}
              detail={`${(latency / Math.max(baselineLatency, 0.01)).toFixed(
                2,
              )}× above baseline`}
              strength="Strong"
            />

            <RcaSignal
              label="Gateway signal"
              value={dominantErrorCode}
              detail="Dominant gateway failure evidence"
              strength="Very strong"
            />

            <RcaSignal
              label="Gateway isolation"
              value={dominantGateway?.key || dominantGateway || "gateway_b"}
              detail="Gateway-specific failure concentration"
              strength="Strong"
            />
          </>
        )}
      </div>

      {/* =====================================================
          COMPETING HYPOTHESES
      ===================================================== */}

      {alternativeHypotheses.length > 0 && (
        <div className="rca-alternatives">
          <div className="rca-section-heading">
            <div>
              <span className="rca-mini-label">COMPETING HYPOTHESES</span>

              <h4>Why other explanations ranked lower</h4>
            </div>

            <span className="rca-evidence-count">
              {alternativeHypotheses.length} alternatives
            </span>
          </div>

          <div className="rca-hypothesis-list">
            {alternativeHypotheses.map((item, index) => {
              const score = Number(item?.score ?? 0);

              return (
                <div
                  className="rca-hypothesis"
                  key={item?.cause || item?.title || index}
                >
                  <div className="rca-hypothesis-info">
                    <span className="rca-hypothesis-rank">#{index + 1}</span>

                    <div>
                      <strong>{item.title || item.cause}</strong>

                      <small>Alternative explanation</small>
                    </div>
                  </div>

                  <div className="rca-hypothesis-score">
                    <strong>{score.toFixed(0)}</strong>

                    <span>score</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* =====================================================
          DECISION
      ===================================================== */}

      <div className="ai-conclusion">
        <div className="rca-conclusion-header">
          <span className="rca-mini-label">FINAL DECISION</span>

          <span className="rca-decision-badge">EVIDENCE-BACKED</span>
        </div>

        <p>
          {primaryRootCause?.description ||
            `Multiple telemetry signals support ${rootCause}.`}
        </p>
      </div>
    </div>
  );
}
function RcaSignal({ label, value, detail, strength }) {
  return (
    <div className="rca-signal">
      <div className="rca-signal-top">
        <span>{label}</span>
        <strong>{strength}</strong>
      </div>

      <h4>{value}</h4>

      <p>{detail}</p>
    </div>
  );
}

function SummaryItem({ label, value }) {
  return (
    <div className="summary-item">
      <span>{label}</span>

      <strong>{value}</strong>
    </div>
  );
}

function DetectionSignal({
  icon,
  label,
  value,
  detail,
  level,
  showBar,
  percentage,
}) {
  return (
    <div className={`detection-signal ${level ? "elevated" : ""}`}>
      <div className="detection-top">
        <div className="detection-icon">{icon}</div>

        {level && <span className="signal-level">{level}</span>}
      </div>

      <span className="detection-label">{label}</span>

      <strong className="detection-value">{value}</strong>

      <span className="detection-detail">{detail}</span>

      {showBar && (
        <div className="detection-bar">
          <div
            style={{
              width: `${Math.min(percentage, 100)}%`,
            }}
          ></div>
        </div>
      )}
    </div>
  );
}

function EvidenceCard({ item, index }) {
  return (
    <div className="evidence-card">
      <div className="evidence-icon">
        {index === 0 ? "↗" : index === 1 ? "◷" : "✓"}
      </div>

      <div className="evidence-content">
        <div className="evidence-top">
          <h3>{getEvidenceTitle(item)}</h3>

          <span className="signal-badge">
            {index === 0 || index === 1 ? "STRONG" : "SIGNAL"}
          </span>
        </div>

        <p>{item}</p>
      </div>
    </div>
  );
}

function BreakdownCard({ title, icon, data }) {
  const entries = Object.entries(data || {});

  const maxValue =
    entries.length > 0
      ? Math.max(...entries.map(([, value]) => Number(value)))
      : 0;

  return (
    <div className="breakdown-card">
      <div className="breakdown-title">
        <div className="breakdown-icon">{icon}</div>

        <div>
          <span>FAILURE RATE</span>

          <h3>{title}</h3>
        </div>
      </div>

      <div className="breakdown-list">
        {entries.length > 0 ? (
          entries.map(([name, value]) => {
            const numericValue = Number(value);

            return (
              <div className="breakdown-row" key={name}>
                <div className="breakdown-label">
                  <span>{name}</span>

                  <strong>{formatPercent(numericValue)}</strong>
                </div>

                <div className="breakdown-track">
                  <div
                    className={
                      numericValue === maxValue
                        ? "breakdown-fill highest"
                        : "breakdown-fill"
                    }
                    style={{
                      width: `${Math.min(numericValue, 100)}%`,
                    }}
                  ></div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="breakdown-empty">No telemetry data available.</div>
        )}
      </div>
    </div>
  );
}

function EvaluationMetric({ label, value, detail, positive }) {
  return (
    <div className="evaluation-metric">
      <span className="evaluation-label">{label}</span>
      <strong className={positive ? "positive" : ""}>{value}</strong>
      <span className="evaluation-detail">{detail}</span>
    </div>
  );
}

function ImprovementCard({ label, value }) {
  return (
    <div className="improvement-card">
      <span>{label}</span>

      <strong>{value}</strong>
    </div>
  );
}

function ProjectionMetric({ label, value }) {
  return (
    <div className="projection-metric">
      <span>{label}</span>

      <strong>{value}</strong>
    </div>
  );
}

/* =========================================================
   HELPERS
========================================================= */

function getHighestEntry(data) {
  const entries = Object.entries(data || {});

  if (!entries.length) {
    return {
      key: "UNKNOWN",
      value: 0,
    };
  }

  let highest = entries[0];

  for (const entry of entries) {
    if (Number(entry[1]) > Number(highest[1])) {
      highest = entry;
    }
  }

  return {
    key: highest[0],
    value: Number(highest[1]),
  };
}

function getDominantErrorCode(evidence, rootCauseCode, rootCause) {
  const text = Array.isArray(evidence) ? evidence.join(" ").toUpperCase() : "";

  const knownCodes = [
    "GATEWAY_TIMEOUT",
    "GATEWAY_ERROR",
    "ISSUER_TIMEOUT",
    "ISSUER_ERROR",
    "UPI_TIMEOUT",
    "UPI_ERROR",
    "NETWORK_ERROR",
  ];

  for (const code of knownCodes) {
    if (text.includes(code)) {
      return code;
    }
  }

  if (
    rootCauseCode === "GATEWAY_DEGRADATION" ||
    String(rootCause).toLowerCase().includes("gateway")
  ) {
    return "GATEWAY_TIMEOUT";
  }

  if (
    rootCauseCode === "ISSUER_DEGRADATION" ||
    String(rootCause).toLowerCase().includes("issuer")
  ) {
    return "ISSUER_ERROR";
  }

  if (
    rootCauseCode === "UPI_DEGRADATION" ||
    String(rootCause).toLowerCase().includes("upi")
  ) {
    return "UPI_ERROR";
  }

  return "UNKNOWN";
}

function formatPercent(value) {
  const numericValue = Number(value ?? 0);

  return `${numericValue.toFixed(2)}%`;
}

function calculateRelativePercentage(current, baseline) {
  if (!baseline || baseline <= 0) {
    return 0;
  }

  const ratio = Number(current) / Number(baseline);

  return Math.min(Math.max(ratio * 50, 8), 100);
}

function calculateRiskScore(
  failureRate,
  baselineFailureRate,
  latency,
  baselineLatency,
) {
  const failureMultiplier = failureRate / Math.max(baselineFailureRate, 0.01);

  const latencyMultiplier = latency / Math.max(baselineLatency, 0.01);

  const failureScore = Math.min(((failureMultiplier - 1) / 2) * 100, 100);

  const latencyScore = Math.min(((latencyMultiplier - 1) / 3) * 100, 100);

  return Math.max(0, Math.min(100, failureScore * 0.55 + latencyScore * 0.45));
}

function getRiskLevel(
  failureRate,
  baselineFailureRate,
  latency,
  baselineLatency,
) {
  const score = calculateRiskScore(
    failureRate,
    baselineFailureRate,
    latency,
    baselineLatency,
  );

  if (score >= 75) {
    return "CRITICAL";
  }

  if (score >= 50) {
    return "HIGH";
  }

  if (score >= 25) {
    return "ELEVATED";
  }

  return "LOW";
}

function calculateProjectedFailureRate(current, baseline, shift) {
  const gap = current - baseline;

  const recoveryFactor = Number(shift) / 100;

  return Math.max(baseline, current - gap * recoveryFactor * 0.58);
}

function calculateProjectedLatency(current, baseline, shift) {
  const gap = current - baseline;

  const recoveryFactor = Number(shift) / 100;

  return Math.max(baseline, current - gap * recoveryFactor * 0.62);
}

function getEvidenceTitle(text) {
  const value = String(text || "").toLowerCase();

  if (value.includes("failure rate")) {
    return "Failure rate spike";
  }

  if (value.includes("latency")) {
    return "Latency degradation";
  }

  if (value.includes("gateway_timeout")) {
    return "Gateway timeout";
  }

  if (value.includes("gateway")) {
    return "Gateway degradation";
  }

  if (value.includes("issuer")) {
    return "Issuer degradation";
  }

  if (value.includes("payment method")) {
    return "Payment method signal";
  }

  return "Telemetry signal";
}

function formatScenarioName(value) {
  return String(value || "")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default App;
