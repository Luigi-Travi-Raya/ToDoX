import type { AppLocale } from './i18n'

export type Priority = 'urgent' | 'high' | 'medium' | 'low' | 'very_low'

export type ChecklistItem = { id: string; nome: string; concluido: boolean }

export type Task = {
  id: string
  nome: string
  prioridade: Priority
  adicionada_em: string
  ordem: number
  tags: string[]
  cores_tags: Record<string, string>
  tempo_acumulado_segundos: number
  cronometro_iniciado_em: string | null
  /** True after the timer has been started at least once, including when paused at 00:00:00. */
  atividade_iniciada: boolean
  completedAt: string | null
  checklist: ChecklistItem[]
}

export type TaskUpdate = {
  revision: number
  history_revision: number
  tasks: Task[]
}

export type TaskState = TaskUpdate & { completed_tasks: Task[] }
export type CompletedTaskUpdate = { history_revision: number; tasks: Task[] }

export type HotkeySettings = {
  ctrl: boolean
  alt: boolean
  shift: boolean
  tecla: string
  tema: 'dark' | 'light'
  locale: AppLocale
  description?: string
}

export type StartupWarning = {
  code: string
  details?: string
}

export class ApiError extends Error {
  constructor(public readonly code: string) {
    super(code)
    this.name = 'ApiError'
  }
}

declare global {
  interface WindowEventMap {
    'tasks-changed': CustomEvent<TaskUpdate>
    'tasks-updated': CustomEvent<TaskUpdate>
  }

  interface Window {
    pywebview?: {
      api: {
        list_tasks(): Promise<Task[]>
        get_task_state(): Promise<TaskState>
        list_completed_tasks(): Promise<CompletedTaskUpdate>
        add_checklist_item(taskId: string, name: string): Promise<TaskUpdate>
        update_checklist_item(taskId: string, itemId: string, name: string): Promise<TaskUpdate>
        set_checklist_item_completed(taskId: string, itemId: string, completed: boolean): Promise<TaskUpdate>
        delete_checklist_item(taskId: string, itemId: string): Promise<TaskUpdate>
        create_task(name: string, priority: Priority): Promise<TaskUpdate>
        update_task_name(taskId: string, name: string): Promise<TaskUpdate>
        update_task_priority(taskId: string, priority: Priority): Promise<TaskUpdate>
        reorder_tasks(orderedTaskIds: string[]): Promise<TaskUpdate>
        complete_task(taskId: string): Promise<TaskUpdate>
        delete_task(taskId: string): Promise<TaskUpdate>
        toggle_task_timer(taskId: string): Promise<TaskUpdate>
        update_task_tags(
          taskId: string,
          tags: string,
          colorOverrides: Record<string, string>,
        ): Promise<TaskUpdate>
        get_settings(): Promise<HotkeySettings>
        save_settings(settings: HotkeySettings): Promise<HotkeySettings>
        get_startup_warnings(): Promise<StartupWarning[]>
        set_settings_open(isOpen: boolean): Promise<void>
        open_quick_add(): Promise<void>
        close_quick_window(): Promise<void>
        close_tray_menu(): Promise<void>
        hide_main_window(): Promise<void>
        show_main_window(): Promise<void>
        exit_app(): Promise<void>
      }
    }
  }
}

type BridgeApi = NonNullable<Window['pywebview']>['api']
let currentTaskUpdate: TaskUpdate | null = null

function acceptTaskUpdate(update: TaskUpdate, authoritative = false): TaskUpdate {
  // Explicit reads also pick up external JSON edits that do not increment the API revision.
  if (
    currentTaskUpdate === null
    || update.revision > currentTaskUpdate.revision
    || (authoritative && update.revision === currentTaskUpdate.revision)
  ) {
    currentTaskUpdate = update
    window.dispatchEvent(new CustomEvent('tasks-updated', { detail: update }))
  }
  return currentTaskUpdate
}

window.addEventListener('tasks-changed', (event) => acceptTaskUpdate(event.detail))

export function getCurrentTaskUpdate(): TaskUpdate | null {
  return currentTaskUpdate
}

function waitForBridge(): Promise<void> {
  if (window.pywebview?.api) return Promise.resolve()

  return new Promise((resolve) => {
    window.addEventListener('pywebviewready', () => resolve(), { once: true })
  })
}

async function callBridge<T>(
  callback: (api: BridgeApi) => Promise<T>,
): Promise<T> {
  await waitForBridge()
  try {
    return await callback(window.pywebview!.api)
  } catch (cause) {
    const message = cause instanceof Error ? cause.message : String(cause)
    const match = message.match(/APP_ERROR:([A-Z0-9_]+)/)
    if (match) throw new ApiError(match[1])
    throw cause
  }
}

async function mutateTasks(callback: (api: BridgeApi) => Promise<TaskUpdate>): Promise<Task[]> {
  const update = await callBridge(callback)
  return acceptTaskUpdate(update).tasks
}

export async function listTasks(): Promise<Task[]> {
  // A native notification received during this unversioned read already has newer data.
  const updateBeforeRead = currentTaskUpdate
  const tasks = await callBridge((api) => api.list_tasks())
  return currentTaskUpdate !== updateBeforeRead && currentTaskUpdate !== null
    ? currentTaskUpdate.tasks
    : tasks
}

export async function getTaskState(): Promise<TaskState> {
  const state = await callBridge((api) => api.get_task_state())
  acceptTaskUpdate(state, true)
  return state
}

export function listCompletedTasks(): Promise<CompletedTaskUpdate> {
  return callBridge((api) => api.list_completed_tasks())
}

export function createTask(name: string, priority: Priority): Promise<Task[]> {
  return mutateTasks((api) => api.create_task(name, priority))
}

export function updateTaskName(taskId: string, name: string): Promise<Task[]> {
  return mutateTasks((api) => api.update_task_name(taskId, name))
}

export function updateTaskPriority(taskId: string, priority: Priority): Promise<Task[]> {
  return mutateTasks((api) => api.update_task_priority(taskId, priority))
}

export function reorderTasks(orderedTaskIds: string[]): Promise<Task[]> {
  return mutateTasks((api) => api.reorder_tasks(orderedTaskIds))
}

export function addChecklistItem(taskId: string, name: string): Promise<Task[]> {
  return mutateTasks((api) => api.add_checklist_item(taskId, name))
}

export function updateChecklistItem(taskId: string, itemId: string, name: string): Promise<Task[]> {
  return mutateTasks((api) => api.update_checklist_item(taskId, itemId, name))
}

export function setChecklistItemCompleted(taskId: string, itemId: string, completed: boolean): Promise<Task[]> {
  return mutateTasks((api) => api.set_checklist_item_completed(taskId, itemId, completed))
}

export function deleteChecklistItem(taskId: string, itemId: string): Promise<Task[]> {
  return mutateTasks((api) => api.delete_checklist_item(taskId, itemId))
}

export function completeTask(taskId: string): Promise<Task[]> {
  return mutateTasks((api) => api.complete_task(taskId))
}

export function deleteTask(taskId: string): Promise<Task[]> {
  return mutateTasks((api) => api.delete_task(taskId))
}

export function toggleTaskTimer(taskId: string): Promise<Task[]> {
  return mutateTasks((api) => api.toggle_task_timer(taskId))
}

export function updateTaskTags(
  taskId: string,
  tags: string,
  colorOverrides: Record<string, string>,
): Promise<Task[]> {
  return mutateTasks((api) => api.update_task_tags(taskId, tags, colorOverrides))
}

export async function getSettings(): Promise<HotkeySettings> {
  return callBridge((api) => api.get_settings())
}

export async function saveSettings(settings: HotkeySettings): Promise<HotkeySettings> {
  return callBridge((api) => api.save_settings(settings))
}

export async function getStartupWarnings(): Promise<StartupWarning[]> {
  return callBridge((api) => api.get_startup_warnings())
}

export async function setSettingsOpen(isOpen: boolean): Promise<void> {
  return callBridge((api) => api.set_settings_open(isOpen))
}

export async function openQuickAdd(): Promise<void> {
  return callBridge((api) => api.open_quick_add())
}

export async function closeQuickWindow(): Promise<void> {
  return callBridge((api) => api.close_quick_window())
}

/** Hides the dedicated `#tray-menu` window without changing the main window state. */
export async function closeTrayMenu(): Promise<void> {
  return callBridge((api) => api.close_tray_menu())
}

export async function hideMainWindow(): Promise<void> {
  return callBridge((api) => api.hide_main_window())
}

export async function showMainWindow(): Promise<void> {
  return callBridge((api) => api.show_main_window())
}

export async function exitApp(): Promise<void> {
  return callBridge((api) => api.exit_app())
}
