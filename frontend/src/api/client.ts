/**
 * React TypeScript API Client for MedOps Orchestrator
 * 
 * Usage in components:
 *   import { useOrchestrator } from './api/client'
 *   
 *   const MyComponent = () => {
 *     const { getScenario, approveRecommendation } = useOrchestrator()
 *     // ...
 *   }
 */

import { useState, useCallback, useEffect } from 'react'

// ============================================================================
// API Types (must match backend models)
// ============================================================================

export interface HealthResponse {
  status: 'ok'
  database: 'connected'
  timestamp: string
}

export interface Scenario {
  id: number
  tag: string
  drug: string
  narrative: string
  approver_role: string
  correlation_id: string
}

export interface ScenarioDetail extends Scenario {
  current_workflow_id?: string
  current_stage?: string
}

export interface RankedOption {
  option_id: string
  label: string
  feasible: boolean
  score?: number
  availability_protection?: number
  lead_time_margin_days?: number
  cost_usd?: number
  waste_avoided_units?: number
  agent_responsible: string
}

export interface RejectedOption {
  option_id: string
  label: string
  reason: string
}

export interface Recommendation {
  recommendation_id: string
  version: number
  drug: string
  problem_type: string
  ranked_options: RankedOption[]
  rejected_options: RejectedOption[]
  scoring_weights: { [key: string]: number }
  input_snapshot: { [key: string]: any }
  policy_version: string
  generated_at: string
}

export interface ApprovalDecision {
  decision_id: string
  workflow_id: string
  recommendation_id: string
  recommendation_version: number
  approver_role: string
  approver_id?: string
  decision: 'approved' | 'rejected' | 'escalated'
  reason?: string
  policy_version: string
  decided_at: string
}

export interface WorkflowState {
  workflow_id: string
  correlation_id: string
  drug: string
  stage: string
  version: number
  detected_at: string
  options_ranked_at?: string
  pending_approval_at?: string
  approved_at?: string
  recommendation?: Recommendation
  approval_decision?: ApprovalDecision
  task_id?: string
}

export interface Task {
  task_id: string
  correlation_id: string
  workflow_id: string
  drug: string
  task_type: 'transfer' | 'procurement'
  status: string
  source_location?: string
  destination_location?: string
  quantity: number
  estimated_delivery_hours?: number
  supplier_name?: string
  estimated_arrival_date?: string
  steps_completed: string[]
  created_at: string
  updated_at: string
  completed_at?: string
}

export interface LatencyMetrics {
  median: number
  p95: number
}

export interface KPIs {
  timestamp: string
  time_window_days: number
  problems_detected: number
  recommendations_generated: number
  recommendation_acceptance_rate_pct: number
  false_positive_rate_pct: number
  latency_detection_to_recommendation_sec: LatencyMetrics
  latency_recommendation_to_approval_sec: LatencyMetrics
  latency_approval_to_task_creation_sec: number
  latency_task_completion_sec: LatencyMetrics
  task_completion_rate_pct: number
  manual_coordination_steps_avoided: number
  estimated_operations_minutes_saved: number
  medication_availability_rate_pct: number
  potential_stockouts_addressed: number
  simulated_stockouts_prevented: number
  expiration_risk_quantity_redistributed: number
  transfer_vs_procurement_ratio: number
  invalid_recommendations_blocked: number
}

export interface Config {
  safety_stock_multiplier: number
  days_of_supply_minimum: number
  expiration_risk_horizon_days: number
  lead_time_buffer_days: number
  scoring_weights: { [key: string]: number }
  minimum_feasibility_score: number
  retry_limit_delivery: number
  minutes_per_manual_coordination_step: number
  updated_at: string
}

// ============================================================================
// API Client Class
// ============================================================================

class MedOpsApiClient {
  private baseUrl: string
  private token?: string

  constructor(baseUrl: string = 'http://localhost:8000', token?: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '') // Remove trailing slash
    this.token = token
  }

  private async request<T>(
    method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
    path: string,
    body?: any
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const options: RequestInit = {
      method,
      headers,
    }

    if (body) {
      options.body = JSON.stringify(body)
    }

    const response = await fetch(url, options)

    if (!response.ok) {
      const error = await response.text()
      throw new Error(`API error ${response.status}: ${error}`)
    }

    return response.json() as Promise<T>
  }

  // System
  async healthCheck(): Promise<HealthResponse> {
    return this.request('GET', '/health')
  }

  // Scenarios
  async listScenarios(): Promise<Scenario[]> {
    return this.request('GET', '/api/v1/scenarios')
  }

  async getScenario(scenarioId: number): Promise<ScenarioDetail> {
    return this.request('GET', `/api/v1/scenarios/${scenarioId}`)
  }

  async runScenario(scenarioId: number, overrideConfig?: any): Promise<{ workflow_id: string; correlation_id: string; status: string; started_at: string }> {
    return this.request('POST', `/api/v1/scenarios/${scenarioId}/run`, {
      override_config: overrideConfig,
    })
  }

  // Workflows
  async getWorkflow(workflowId: string): Promise<WorkflowState> {
    return this.request('GET', `/api/v1/workflows/${workflowId}`)
  }

  async approveRecommendation(
    workflowId: string,
    approverRole: string,
    approverId?: string
  ): Promise<{ workflow_id: string; status: string; task_id?: string; task_status?: string; timestamp: string }> {
    return this.request('POST', `/api/v1/workflows/${workflowId}/approve`, {
      approver_role: approverRole,
      approver_id: approverId,
    })
  }

  async rejectRecommendation(
    workflowId: string,
    approverRole: string,
    reason: string,
    approverId?: string
  ): Promise<{ workflow_id: string; status: string; rejection_count: number; next_version?: number; timestamp: string }> {
    return this.request('POST', `/api/v1/workflows/${workflowId}/reject`, {
      approver_role: approverRole,
      approver_id: approverId,
      reason,
    })
  }

  async escalateWorkflow(workflowId: string, reason: string): Promise<{ workflow_id: string; status: string; timestamp: string }> {
    return this.request('POST', `/api/v1/workflows/${workflowId}/escalate`, {
      reason,
    })
  }

  // Tasks
  async getTask(taskId: string): Promise<Task> {
    return this.request('GET', `/api/v1/tasks/${taskId}`)
  }

  async reassignTask(taskId: string): Promise<{ task_id: string; status: string; timestamp: string }> {
    return this.request('POST', `/api/v1/tasks/${taskId}/reassign`, {})
  }

  // KPI
  async getKPIs(timeWindowDays: number = 1): Promise<KPIs> {
    return this.request('GET', `/api/v1/kpi?time_window_days=${timeWindowDays}`)
  }

  // Audit
  async getAuditTrail(limit: number = 50, offset: number = 0): Promise<{ total: number; items: ApprovalDecision[] }> {
    return this.request('GET', `/api/v1/audit?limit=${limit}&offset=${offset}`)
  }

  // Config
  async getConfig(): Promise<Config> {
    return this.request('GET', `/api/v1/config`)
  }

  async updateConfig(config: Partial<Config>): Promise<Config> {
    return this.request('PATCH', `/api/v1/config`, config)
  }
}

// ============================================================================
// React Hooks
// ============================================================================

export const createApiClient = (baseUrl?: string, token?: string) => {
  return new MedOpsApiClient(baseUrl, token)
}

/**
 * Main hook for orchestrator operations
 */
export const useOrchestrator = (baseUrl?: string) => {
  const [client] = useState(() => new MedOpsApiClient(baseUrl))
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null)
  const [task, setTask] = useState<Task | null>(null)
  const [kpis, setKpis] = useState<KPIs | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch scenarios
  const fetchScenarios = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await client.listScenarios()
      setScenarios(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [client])

  // Fetch workflow
  const fetchWorkflow = useCallback(async (workflowId: string) => {
    try {
      setLoading(true)
      setError(null)
      const data = await client.getWorkflow(workflowId)
      setWorkflow(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [client])

  // Run scenario
  const runScenario = useCallback(async (scenarioId: number) => {
    try {
      setLoading(true)
      setError(null)
      const result = await client.runScenario(scenarioId)
      // Poll for workflow state
      await new Promise(r => setTimeout(r, 1000))
      await fetchWorkflow(result.workflow_id)
      return result.workflow_id
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      throw err
    } finally {
      setLoading(false)
    }
  }, [client, fetchWorkflow])

  // Approve
  const approve = useCallback(async (workflowId: string, approverRole: string, approverId?: string) => {
    try {
      setLoading(true)
      setError(null)
      const result = await client.approveRecommendation(workflowId, approverRole, approverId)
      if (result.task_id) {
        setTask({ task_id: result.task_id, ...workflow } as Task)
      }
      await fetchWorkflow(workflowId)
      return result
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      throw err
    } finally {
      setLoading(false)
    }
  }, [client, workflow, fetchWorkflow])

  // Reject
  const reject = useCallback(async (workflowId: string, approverRole: string, reason: string, approverId?: string) => {
    try {
      setLoading(true)
      setError(null)
      const result = await client.rejectRecommendation(workflowId, approverRole, reason, approverId)
      await new Promise(r => setTimeout(r, 500))
      await fetchWorkflow(workflowId)
      return result
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      throw err
    } finally {
      setLoading(false)
    }
  }, [client, fetchWorkflow])

  // Fetch KPIs
  const fetchKPIs = useCallback(async (timeWindowDays: number = 1) => {
    try {
      setLoading(true)
      setError(null)
      const data = await client.getKPIs(timeWindowDays)
      setKpis(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [client])

  return {
    // State
    scenarios,
    workflow,
    task,
    kpis,
    loading,
    error,
    
    // Methods
    client,
    fetchScenarios,
    fetchWorkflow,
    fetchKPIs,
    runScenario,
    approve,
    reject,
  }
}

/**
 * Hook for polling workflow state at intervals
 */
export const useWorkflowPoller = (workflowId?: string, intervalMs: number = 1000) => {
  const { fetchWorkflow, workflow } = useOrchestrator()

  useEffect(() => {
    if (!workflowId) return

    // Initial fetch
    fetchWorkflow(workflowId)

    // Poll
    const timer = setInterval(() => {
      fetchWorkflow(workflowId)
    }, intervalMs)

    return () => clearInterval(timer)
  }, [workflowId, intervalMs, fetchWorkflow])

  return workflow
}

/**
 * Hook for KPI polling
 */
export const useKPIPoller = (intervalMs: number = 5000) => {
  const { fetchKPIs, kpis } = useOrchestrator()

  useEffect(() => {
    // Initial fetch
    fetchKPIs()

    // Poll
    const timer = setInterval(() => {
      fetchKPIs()
    }, intervalMs)

    return () => clearInterval(timer)
  }, [intervalMs, fetchKPIs])

  return kpis
}

export default MedOpsApiClient
