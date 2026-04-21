export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000"

export type StageStatus = "pending" | "running" | "succeeded" | "failed"
export type TaskStatus = "queued" | "running" | "succeeded" | "failed"

export type TaskStage = {
  task_id: string
  name: string
  label: string
  status: StageStatus
  started_at: string | null
  completed_at: string | null
  last_message: string | null
  error_message: string | null
}

export type Task = {
  id: string
  url: string
  status: TaskStatus
  current_stage: string | null
  session_path: string | null
  final_video_path: string | null
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  stages: TaskStage[]
}

export type CookieInfo = {
  exists: boolean
  size: number
  updated_at: number | null
  content: string
}

export type OpenAISettings = {
  base_url: string
  api_key: string
  has_api_key: boolean
  model: string
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    cache: "no-store",
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed: ${response.status}`)
  }
  return response.json()
}

export function getCurrentTask() {
  return request<Task | null>("/api/tasks/current")
}

export function createTask(url: string) {
  return request<Task>("/api/tasks", {
    method: "POST",
    body: JSON.stringify({ url }),
  })
}

export function getCookieInfo() {
  return request<CookieInfo>("/api/cookies/youtube")
}

export function saveCookie(content: string) {
  return request<CookieInfo>("/api/cookies/youtube", {
    method: "POST",
    body: JSON.stringify({ content }),
  })
}

export function getOpenAISettings() {
  return request<OpenAISettings>("/api/settings/openai")
}

export function saveOpenAISettings(settings: {
  base_url: string
  api_key: string
  model: string
}) {
  return request<OpenAISettings>("/api/settings/openai", {
    method: "POST",
    body: JSON.stringify(settings),
  })
}

export function finalVideoUrl(taskId: string) {
  return `${API_BASE}/api/tasks/${taskId}/artifact/final-video`
}

