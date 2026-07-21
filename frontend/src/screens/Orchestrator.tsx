import React, { useState, useEffect, useRef } from 'react';
import {
  PackageX, Warehouse, Clock, Truck, ShoppingCart, ShieldCheck,
  CheckCircle2, XCircle, ChevronRight, Radio, Activity, Loader2,
  AlertTriangle, RotateCcw, GitBranch, Hash, UserCheck, Info, Ban,
} from 'lucide-react';
import { useOrchestrator, useWorkflowPoller, useKPIPoller, Scenario, WorkflowState, KPIs } from './api_client';

/* Same token system as before */
const C = {
  bg: '#0F141B', panel: '#171F29', panelAlt: '#1D2733', border: '#28323F',
  text: '#EDEFF2', muted: '#8A94A6', muted2: '#5C6779',
  amber: '#E8A33D', red: '#D9524B', blue: '#4C86C7', purple: '#9B7FD4', teal: '#4FA88A',
};

const STEP_PATH = ['detected', 'agents_consulted', 'options_ranked', 'pending_approval', 'approved', 'task_created', 'in_progress', 'completed'];
const STEP_LABEL = {
  detected: 'Detected', agents_consulted: 'Agents Consulted', options_ranked: 'Options Ranked',
  pending_approval: 'Pending Approval', approved: 'Approved', task_created: 'Task Created',
  in_progress: 'In Progress', completed: 'Completed', rejected: 'Rejected', escalated: 'Escalated',
};

const REJECT_REASONS = [
  'Insufficient lead-time margin',
  'Cost exceeds budget threshold',
  'Prefer alternate supplier',
  'Clinical / operational override',
  'Other — needs review',
];

export default function MedOpsOrchestratorWithRealAPI() {
  const apiBaseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  const { scenarios, workflow, loading, error, fetchScenarios, runScenario, approve, reject } = useOrchestrator(apiBaseUrl);

  const [selectedScenarioId, setSelectedScenarioId] = useState<number | null>(null);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [approverRole, setApproverRole] = useState('');
  const [clock, setClock] = useState(new Date());

  // Auto-update clock
  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Fetch scenarios on mount
  useEffect(() => {
    fetchScenarios().catch(err => console.error('Failed to load scenarios:', err));
  }, [fetchScenarios]);

  // Poll workflow state if one is selected
  const polledWorkflow = useWorkflowPoller(selectedWorkflowId, 1000);
  const effectiveWorkflow = polledWorkflow || workflow;

  // Poll KPIs
  const kpis = useKPIPoller(5000);

  const handleRunScenario = async (scenarioId: number) => {
    try {
      const workflowId = await runScenario(scenarioId);
      setSelectedScenarioId(scenarioId);
      setSelectedWorkflowId(workflowId);
    } catch (err) {
      console.error('Failed to run scenario:', err);
      alert(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const handleApprove = async () => {
    if (!selectedWorkflowId || !approverRole) {
      alert('Please select an approver role');
      return;
    }
    try {
      await approve(selectedWorkflowId, approverRole);
      setApproverRole('');
    } catch (err) {
      console.error('Failed to approve:', err);
      alert(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const handleReject = async () => {
    if (!selectedWorkflowId || !approverRole || !rejectReason) {
      alert('Please fill in approver role and rejection reason');
      return;
    }
    try {
      await reject(selectedWorkflowId, approverRole, rejectReason);
      setApproverRole('');
      setRejectReason('');
    } catch (err) {
      console.error('Failed to reject:', err);
      alert(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  return (
    <div style={{ background: C.bg, color: C.text, minHeight: '100vh', fontFamily: "'IBM Plex Sans', sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
        * { box-sizing: border-box; }
        .disp { font-family: 'Space Grotesk', sans-serif; }
        .mono { font-family: 'IBM Plex Mono', monospace; }
        .pulse { animation: pulse 1.8s ease-in-out infinite; }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .35; } }
        .spin { animation: spin 1.1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .fade-in { animation: fadeIn .3s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
        button:hover { filter: brightness(1.12); }
        select { background: ${C.bg}; color: ${C.text}; border: 1px solid ${C.border}; border-radius: 6px; padding: 6px 8px; font-size: 12px; }
      `}</style>

      {/* Top bar */}
      <div style={{ borderBottom: `1px solid ${C.border}`, padding: '14px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, background: C.panel }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ShieldCheck size={22} color={C.teal} />
          <div>
            <div className="disp" style={{ fontSize: 16, fontWeight: 700 }}>MedOps Orchestrator</div>
            <div className="mono" style={{ fontSize: 10.5, color: C.muted }}>real API • ranked options • human approval</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span className="mono" style={{ fontSize: 10, color: C.muted2, border: `1px solid ${C.border}`, borderRadius: 4, padding: '3px 7px' }}>API: {apiBaseUrl}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="pulse" style={{ width: 7, height: 7, borderRadius: '50%', background: error ? C.red : C.teal, display: 'inline-block' }} />
            <span className="mono" style={{ fontSize: 11, color: error ? C.red : C.teal }}>{error ? 'ERROR' : 'CONNECTED'}</span>
          </div>
          <div className="mono" style={{ fontSize: 12, color: C.muted }}>{clock.toLocaleTimeString('en-US', { hour12: false })}</div>
        </div>
      </div>

      {error && (
        <div style={{ background: C.red + '22', border: `1px solid ${C.red}`, color: C.red, padding: '12px 20px', fontSize: 12 }}>
          <b>API Error:</b> {error} — Make sure backend is running at {apiBaseUrl}
        </div>
      )}

      <div style={{ maxWidth: 1240, margin: '0 auto', padding: '20px 20px 40px' }}>

        {/* KPI section */}
        {kpis && (
          <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16, marginBottom: 18 }}>
            <div style={{ marginBottom: 12 }}>
              <SectionTitle>Operational KPIs</SectionTitle>
              <span className="mono" style={{ fontSize: 10, color: C.muted2 }}>from event log • real-time updates</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10 }}>
              <Kpi label="Problems detected" value={String(kpis.problems_detected)} tone={C.blue} />
              <Kpi label="Recommendations" value={String(kpis.recommendations_generated)} tone={C.amber} />
              <Kpi label="Acceptance rate" value={`${kpis.recommendation_acceptance_rate_pct.toFixed(0)}%`} tone={C.teal} />
              <Kpi label="Avg decision time" value={`${kpis.latency_recommendation_to_approval_sec.median.toFixed(0)}s`} tone={C.purple} />
              <Kpi label="Tasks completed" value={`${kpis.task_completion_rate_pct.toFixed(0)}%`} tone={C.teal} />
              <Kpi label="Mins saved" value={`${kpis.estimated_operations_minutes_saved.toFixed(0)}`} tone={C.blue} />
            </div>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16 }}>

          {/* Scenario selector */}
          <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, padding: 12 }}>
            <SectionTitle>Scenarios</SectionTitle>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
              {loading && scenarios.length === 0 && (
                <div style={{ fontSize: 11, color: C.muted, padding: 10 }}>
                  <Loader2 size={12} className="spin" style={{ marginRight: 6 }} /> Loading scenarios…
                </div>
              )}
              {scenarios.map((s) => (
                <button key={s.id} onClick={() => handleRunScenario(s.id)}
                  style={{
                    textAlign: 'left', background: selectedScenarioId === s.id ? C.panelAlt : 'transparent',
                    border: `1px solid ${selectedScenarioId === s.id ? C.teal : C.border}`, borderRadius: 8,
                    padding: '9px 10px', cursor: loading ? 'not-allowed' : 'pointer', color: C.text, fontSize: 11,
                    opacity: loading && selectedScenarioId !== s.id ? 0.6 : 1,
                  }}>
                  <span style={{ fontWeight: 600 }}>Scenario {s.id}</span>
                  <div style={{ fontSize: 10, color: C.muted, marginTop: 3 }}>{s.tag}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Main workflow panel */}
          {effectiveWorkflow ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, padding: 18 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
                  <span className="disp" style={{ fontSize: 14.5, fontWeight: 700 }}>{effectiveWorkflow.drug}</span>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <MetaChip text={`v${effectiveWorkflow.version}`} />
                    <MetaChip text={effectiveWorkflow.correlation_id} />
                  </div>
                </div>

                <Stepper stage={effectiveWorkflow.stage} />

                {/* Ranked options */}
                {effectiveWorkflow.recommendation && (
                  <div style={{ marginTop: 14, background: C.panelAlt, border: `1px solid ${C.border}`, borderRadius: 8, padding: 12 }}>
                    <div className="mono" style={{ fontSize: 9.5, color: C.muted2, marginBottom: 8 }}>RANKED OPTIONS</div>
                    {effectiveWorkflow.recommendation.ranked_options.filter(o => o.feasible).map((o, i) => (
                      <div key={o.option_id} style={{ fontSize: 11, marginBottom: i < effectiveWorkflow.recommendation!.ranked_options.length - 1 ? 8 : 0 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span>{i === 0 && '★ '}{o.label}</span>
                          <span style={{ color: i === 0 ? C.teal : C.muted, fontWeight: i === 0 ? 600 : 400 }}>{o.score}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Approval section */}
                {effectiveWorkflow.stage === 'pending_approval' && (
                  <div style={{ marginTop: 14, background: C.panelAlt, border: `1px solid ${C.amber}`, borderRadius: 8, padding: 12 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 10 }}>Approve or reject?</div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                      <select value={approverRole} onChange={(e) => setApproverRole(e.target.value)}>
                        <option value="">Approver role…</option>
                        <option value="Manager">Manager</option>
                        <option value="Pharmacist">Pharmacist</option>
                        <option value="Clinician">Clinician</option>
                      </select>
                      <select value={rejectReason} onChange={(e) => setRejectReason(e.target.value)}>
                        <option value="">Rejection reason (for reject)…</option>
                        {REJECT_REASONS.map(r => <option key={r} value={r}>{r}</option>)}
                      </select>
                      <button onClick={handleApprove} disabled={!approverRole || loading}
                        style={{ background: C.teal, color: '#0F141B', border: 'none', borderRadius: 6, padding: '7px 14px', fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.6 : 1 }}>
                        {loading ? <Loader2 size={12} className="spin" /> : 'Approve'}
                      </button>
                      <button onClick={handleReject} disabled={!approverRole || !rejectReason || loading}
                        style={{ background: 'transparent', color: C.red, border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 12px', cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.6 : 1 }}>
                        Reject
                      </button>
                    </div>
                  </div>
                )}

                {/* Status badge */}
                <div style={{ marginTop: 12 }}>
                  <span className="mono" style={{ fontSize: 9.5, color: C.muted2, border: `1px solid ${C.border}`, borderRadius: 4, padding: '3px 6px' }}>
                    {STEP_LABEL[effectiveWorkflow.stage as keyof typeof STEP_LABEL]}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, padding: 18, textAlign: 'center', color: C.muted2 }}>
              <p>Select a scenario from the left to start</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* Components */
function Stepper({ stage }: { stage: string }) {
  const idx = STEP_PATH.indexOf(stage);
  return (
    <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 4, marginTop: 10, borderTop: `1px solid ${C.border}`, paddingTop: 10 }}>
      {STEP_PATH.map((s, i) => {
        const done = idx >= 0 && i <= idx;
        const current = i === idx;
        return (
          <React.Fragment key={s}>
            <div style={{
              fontSize: 9, padding: '4px 7px', borderRadius: 5, whiteSpace: 'nowrap',
              background: current ? C.amber : done ? '#20303020' : 'transparent',
              border: `1px solid ${current ? C.amber : done ? C.teal : C.border}`,
              color: current ? '#0F141B' : done ? C.teal : C.muted2, fontWeight: current ? 700 : 500,
            }}>{STEP_LABEL[s as keyof typeof STEP_LABEL]}</div>
            {i < STEP_PATH.length - 1 && <ChevronRight size={10} color={C.muted2} />}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <div className="disp" style={{ fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
    <Radio size={12} color={C.muted} /> {children}
  </div>;
}

function MetaChip({ text }: { text: string }) {
  return (
    <div className="mono" style={{ fontSize: 9.5, color: C.muted, background: C.panelAlt, border: `1px solid ${C.border}`, borderRadius: 6, padding: '3px 7px' }}>
      {text}
    </div>
  );
}
