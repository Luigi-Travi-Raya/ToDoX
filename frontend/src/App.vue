<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import QuickAdd from './QuickAdd.vue'
import TrayMenu from './TrayMenu.vue'
import PrioritySelect from './PrioritySelect.vue'
import TaskChecklist from './TaskChecklist.vue'
import playIcon from '../../../assets/icons/play.svg'
import pauseIcon from '../../../assets/icons/pause.svg'
import completeIcon from '../../../assets/icons/complete.svg'
import deleteIcon from '../../../assets/icons/delete.svg'
import { applyTheme } from './theme'
import {
  exitApp,
  getSettings,
  getStartupWarnings,
  hideMainWindow,
  completeTask,
  createTask,
  deleteTask,
  getCurrentTaskUpdate,
  getTaskState,
  listCompletedTasks,
  reorderTasks,
  toggleTaskTimer,
  saveSettings,
  setSettingsOpen,
  updateTaskTags,
  updateTaskName,
  updateTaskPriority,
  type Task,
  type TaskUpdate,
  type HotkeySettings,
  type Priority,
  type StartupWarning,
} from './api'
import { setAppLocale, supportedLocales, type AppLocale } from './i18n'
import { translatedError } from './i18n/errors'

const { locale, t, te } = useI18n()
const quickMode = window.location.hash === '#quick-add'
const trayMode = window.location.hash === '#tray-menu'
const tasks = ref<Task[]>([])
const completedTasks = ref<Task[]>([])
const loading = ref(true)
const dataAvailable = ref(true)
const saving = ref(false)
const busyTaskId = ref('')
const checklistExpanded = ref<Record<string, boolean>>({})
const checklistBusy = ref<Record<string, boolean>>({})
const checklistPanels = new Map<string, { prepareAction: () => Promise<boolean> }>()
const error = ref('')
const name = ref('')
const priority = ref<Priority>('medium')
const mode = ref<'active' | 'completed'>('active')
const selectedTags = ref<string[]>([])
const editingNameTaskId = ref('')
const editedName = ref('')
const nameEditorError = ref('')
const editingTask = ref<Task | null>(null)
const editedTags = ref('')
const editedTagColors = ref<Record<string, string>>({})
const lastValidEditedTags = ref<string[]>([])
const editorError = ref('')
const settingsOpen = ref(false)
const settingsSaving = ref(false)
const settingsError = ref('')
const settings = ref<HotkeySettings>({ ctrl: true, alt: true, shift: false, tecla: 'T', tema: 'dark', locale: 'en' })
const persistedLocale = ref<AppLocale>('en')
const closeDialogOpen = ref(false)
const startupWarnings = ref<StartupWarning[]>([])
const draggedTaskId = ref('')
const dragTaskOrder = ref<string[] | null>(null)
const hotkeyKeys = [...'ABCDEFGHIJKLMNOPQRSTUVWXYZ', ...Array.from({ length: 12 }, (_, index) => `F${index + 1}`)]
const tagTokenPattern = /^#[\p{L}\p{N}_-]+$/u
const tagColorPattern = /^#[\da-f]{6}$/i
const lightTagTextColor = '#F6EFE4'
const now = ref(Date.now())
let clock: number | undefined
let resettingTagEditor = false
let dragPreview: HTMLElement | null = null
let preservingDragTaskOrder = false
let taskStateLoaded = false
let disposed = false
let historyRevision = -1
let targetHistoryRevision = -1
let historyGeneration = 0
let stateRefresh: Promise<void> | null = null
let historyRefresh: Promise<void> | null = null

const sourceTasks = computed(() => (mode.value === 'active' ? tasks.value : completedTasks.value))
const currentDate = computed(() =>
  new Intl.DateTimeFormat(locale.value, { day: '2-digit', month: '2-digit' }).format(now.value),
)
const currentDateTime = computed(() => {
  const current = new Date(now.value)
  const year = current.getFullYear()
  const month = String(current.getMonth() + 1).padStart(2, '0')
  const day = String(current.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
})
const visuallyOrderedSourceTasks = computed(() => {
  const order = dragTaskOrder.value
  if (mode.value !== 'active' || order === null) return sourceTasks.value
  const rank = new Map(order.map((taskId, index) => [taskId, index]))
  return [...sourceTasks.value].sort(
    (first, second) =>
      (rank.get(first.id) ?? Number.MAX_SAFE_INTEGER)
      - (rank.get(second.id) ?? Number.MAX_SAFE_INTEGER),
  )
})
const availableTags = computed(() =>
  [...new Set(sourceTasks.value.flatMap((task) => task.tags))].sort((a, b) => a.localeCompare(b)),
)
const visibleTasks = computed(() => {
  if (selectedTags.value.length === 0) return visuallyOrderedSourceTasks.value
  return visuallyOrderedSourceTasks.value.filter((task) =>
    task.tags.some((tag) => selectedTags.value.includes(tag)),
  )
})
const visibleTasksByPriority = computed(() => {
  const groups: Record<Priority, Task[]> = { urgent: [], high: [], medium: [], low: [], very_low: [] }
  for (const task of visibleTasks.value) groups[task.prioridade].push(task)
  return groups
})
const anyChecklistBusy = computed(() => Object.values(checklistBusy.value).some(Boolean))
const parsedEditedTags = computed(() => parseEditorTags(editedTags.value))
const editorTags = computed(() => parsedEditedTags.value ?? [])
const editedTagsAreValid = computed(() => parsedEditedTags.value !== null)

watch(visibleTasks, (next, previous) => {
  const focusedCard = document.activeElement instanceof Element
    ? document.activeElement.closest<HTMLElement>('.task-card') : null
  const focusedId = focusedCard?.dataset.taskId
  if (!focusedId || next.some((task) => task.id === focusedId)) return
  const previousIndex = previous.findIndex((task) => task.id === focusedId)
  const replacement = next[Math.min(Math.max(previousIndex, 0), next.length - 1)]
  void nextTick(() => {
    const card = replacement
      ? [...document.querySelectorAll<HTMLElement>('.task-card')]
        .find((element) => element.dataset.taskId === replacement.id) : undefined
    const target = card?.querySelector<HTMLElement>('.task-name-button, .checklist-summary')
      ?? card
      ?? document.querySelector<HTMLElement>('.new-task input, .active-tab')
    target?.focus()
  })
})

watch(
  parsedEditedTags,
  (tags) => {
    if (resettingTagEditor || tags === null) return
    reconcileEditedTagColors(tags)
    editorError.value = ''
  },
  { flush: 'sync' },
)

function switchMode(nextMode: 'active' | 'completed') {
  cancelNameEdit()
  mode.value = nextMode
  selectedTags.value = []
  error.value = ''
  if (nextMode === 'completed') refreshHistoryInBackground()
}

async function startNameEdit(task: Task) {
  if (mode.value !== 'active' || !await prepareTaskMutation(task.id)) return
  editingNameTaskId.value = task.id
  editedName.value = task.nome
  nameEditorError.value = ''
  void nextTick(() => {
    const input = document.querySelector<HTMLInputElement>('.task-name-input')
    input?.focus()
    input?.select()
  })
}

function cancelNameEdit() {
  editingNameTaskId.value = ''
  editedName.value = ''
  nameEditorError.value = ''
}

async function saveTaskName(task: Task) {
  if (editingNameTaskId.value !== task.id || busyTaskId.value) return

  const nextName = editedName.value.trim()
  if (!nextName) {
    nameEditorError.value = t('errors.TASK_NAME_REQUIRED')
    return
  }
  if (nextName === task.nome) {
    cancelNameEdit()
    return
  }

  busyTaskId.value = task.id
  nameEditorError.value = ''
  try {
    await updateTaskName(task.id, nextName)
    cancelNameEdit()
  } catch (cause) {
    nameEditorError.value = translatedError(t, cause, 'errors.saveTaskName')
  } finally {
    busyTaskId.value = ''
  }
}

function toggleTag(tag: string) {
  selectedTags.value = selectedTags.value.includes(tag)
    ? selectedTags.value.filter((item) => item !== tag)
    : [...selectedTags.value, tag]
}

function tagStyle(task: Task, tag: string) {
  return tagColorStyle(task.cores_tags[tag])
}

function filterTagStyle(tag: string) {
  const task = sourceTasks.value.find((item) => item.tags.includes(tag))
  return task ? tagStyle(task, tag) : undefined
}

function parseEditorTags(value: string): string[] | null {
  if (!value.trim()) return []

  const tags: string[] = []
  for (const token of value.trim().split(/\s+/)) {
    if (!tagTokenPattern.test(token)) return null
    const tag = token.slice(1).toLocaleLowerCase(locale.value)
    if (!tags.includes(tag)) tags.push(tag)
  }
  return tags
}

function knownTagColor(tag: string): string | undefined {
  for (const taskList of [tasks.value, completedTasks.value]) {
    for (const task of taskList) {
      if (Object.hasOwn(task.cores_tags, tag)) return task.cores_tags[tag]
    }
  }
  return undefined
}

function randomTagColor(): string {
  const colorBytes = new Uint8Array(3)
  window.crypto.getRandomValues(colorBytes)
  return `#${Array.from(colorBytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`.toUpperCase()
}

function relativeLuminance(color: string): number {
  const channels = [1, 3, 5].map((offset) => {
    const channel = Number.parseInt(color.slice(offset, offset + 2), 16) / 255
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
}

function accessibleTextColor(backgroundColor: string): '#000000' | '#F6EFE4' {
  const luminance = relativeLuminance(backgroundColor)
  const contrastWithBlack = (luminance + 0.05) / 0.05
  const contrastWithCream =
    (relativeLuminance(lightTagTextColor) + 0.05) / (luminance + 0.05)
  return contrastWithBlack >= contrastWithCream ? '#000000' : lightTagTextColor
}

function tagColorStyle(backgroundColor: string) {
  return {
    '--tag-background': backgroundColor,
    '--tag-color': accessibleTextColor(backgroundColor),
  }
}

function reconcileEditedTagColors(tags: string[]) {
  const previousTags = lastValidEditedTags.value
  const colors: Record<string, string> = Object.assign(Object.create(null), editedTagColors.value)

  tags.forEach((tag, index) => {
    if (Object.hasOwn(colors, tag)) return

    const existingColor = knownTagColor(tag)
    if (existingColor) {
      colors[tag] = existingColor
      return
    }

    const previousTag = previousTags[index]
    const previousColor = previousTag ? colors[previousTag] : undefined
    if (previousTag && !tags.includes(previousTag) && previousColor !== undefined) {
      colors[tag] = previousColor
      return
    }

    colors[tag] = randomTagColor()
  })

  editedTagColors.value = colors
  lastValidEditedTags.value = [...tags]
}

function editedTagStyle(tag: string) {
  return tagColorStyle(editedTagColors.value[tag])
}

function updateEditedTagColor(tag: string, event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement) || !tagColorPattern.test(target.value)) return
  editedTagColors.value = { ...editedTagColors.value, [tag]: target.value.toUpperCase() }
}

async function openTagEditor(task: Task) {
  if (mode.value !== 'active' || !await prepareTaskMutation(task.id)) return
  resettingTagEditor = true
  editingTask.value = task
  editedTagColors.value = Object.fromEntries(
    task.tags.map((tag) => [tag, task.cores_tags[tag]]),
  )
  lastValidEditedTags.value = [...task.tags]
  editedTags.value = task.tags.map((tag) => `#${tag}`).join(' ')
  resettingTagEditor = false
  editorError.value = ''
}

function closeTagEditor() {
  resettingTagEditor = true
  editingTask.value = null
  editedTags.value = ''
  editedTagColors.value = {}
  lastValidEditedTags.value = []
  resettingTagEditor = false
  editorError.value = ''
}

async function openSettings() {
  settingsError.value = ''
  try {
    settings.value = await getSettings()
    persistedLocale.value = settings.value.locale
    setAppLocale(settings.value.locale)
    await setSettingsOpen(true)
    settingsOpen.value = true
  } catch (cause) {
    error.value = translatedError(t, cause, 'errors.loadSettings')
  }
}

async function closeSettings(restoreLocale = true) {
  if (restoreLocale) setAppLocale(persistedLocale.value)
  settingsOpen.value = false
  settingsError.value = ''
  await setSettingsOpen(false)
}

function restoreDefaultHotkey() {
  settings.value = {
    ctrl: true,
    alt: true,
    shift: false,
    tecla: 'T',
    tema: settings.value.tema,
    locale: settings.value.locale,
  }
}

async function submitSettings() {
  settingsSaving.value = true
  settingsError.value = ''
  try {
    settings.value = await saveSettings({ ...settings.value })
    applyTheme(settings.value.tema)
    persistedLocale.value = setAppLocale(settings.value.locale)
    await closeSettings(false)
  } catch (cause) {
    settingsError.value = translatedError(t, cause, 'errors.saveSettings')
  } finally {
    settingsSaving.value = false
  }
}

function applyTaskUpdate(update: TaskUpdate) {
  tasks.value = update.tasks
  dataAvailable.value = true
  targetHistoryRevision = Math.max(targetHistoryRevision, update.history_revision)
  refreshHistoryInBackground()
}

function onTasksUpdated(event: CustomEvent<TaskUpdate>) {
  applyTaskUpdate(event.detail)
}

function refreshHistoryInBackground() {
  if (
    disposed || !taskStateLoaded || stateRefresh !== null || historyRefresh !== null
    || historyRevision >= targetHistoryRevision
  ) return

  historyRefresh = (async () => {
    try {
      while (!disposed && stateRefresh === null && historyRevision < targetHistoryRevision) {
        const generation = historyGeneration
        const update = await listCompletedTasks()
        if (disposed) return
        if (generation !== historyGeneration || update.history_revision < targetHistoryRevision) continue
        completedTasks.value = update.tasks
        historyRevision = update.history_revision
      }
    } catch (cause) {
      if (!disposed) error.value = translatedError(t, cause, 'errors.refreshTasks')
    } finally {
      historyRefresh = null
    }
  })()
}

function refreshTasks(): Promise<void> {
  if (stateRefresh !== null) return stateRefresh
  // Discard history responses started before this authoritative snapshot.
  historyGeneration += 1
  stateRefresh = (async () => {
    const state = await getTaskState()
    if (disposed) return
    applyTaskUpdate(getCurrentTaskUpdate()!)
    if (state.history_revision >= targetHistoryRevision && state.history_revision >= historyRevision) {
      completedTasks.value = state.completed_tasks
      historyRevision = state.history_revision
    }
    taskStateLoaded = true
  })().finally(() => {
    stateRefresh = null
    refreshHistoryInBackground()
  })
  return stateRefresh
}

function onTasksRefreshRequested() {
  void refreshTasks().catch((cause) => {
    if (disposed) return
    dataAvailable.value = false
    error.value = translatedError(t, cause, 'errors.refreshTasks')
  })
}

function onCloseRequested() {
  closeDialogOpen.value = true
}

function onWindowKeydown(event: KeyboardEvent) {
  if (event.key !== 'Escape') return
  if (closeDialogOpen.value) {
    closeDialogOpen.value = false
  } else if (settingsOpen.value) {
    void closeSettings()
  } else if (editingTask.value) {
    closeTagEditor()
  } else if (editingNameTaskId.value) {
    cancelNameEdit()
  }
}

async function keepInBackground() {
  closeDialogOpen.value = false
  editingTask.value = null
  if (settingsOpen.value) await closeSettings()
  await hideMainWindow()
}

async function saveTags() {
  if (!editingTask.value) return
  const tags = parsedEditedTags.value
  if (tags === null) {
    editorError.value = t('tags.formatError')
    return
  }

  busyTaskId.value = editingTask.value.id
  editorError.value = ''
  try {
    const colorOverrides = Object.fromEntries(
      tags.map((tag) => [tag, editedTagColors.value[tag]]),
    )
    await updateTaskTags(editingTask.value.id, editedTags.value, colorOverrides)
    selectedTags.value = selectedTags.value.filter((tag) => availableTags.value.includes(tag))
    closeTagEditor()
  } catch (cause) {
    editorError.value = translatedError(t, cause, 'errors.saveTags')
  } finally {
    busyTaskId.value = ''
  }
}

function taskSeconds(task: Task) {
  let seconds = task.tempo_acumulado_segundos
  if (task.cronometro_iniciado_em) {
    seconds += Math.max(0, Math.floor((now.value - Date.parse(task.cronometro_iniciado_em)) / 1000))
  }
  return seconds
}

function formatTime(task: Task) {
  const totalMinutes = Math.floor(taskSeconds(task) / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

function formatDate(value: string | null) {
  return value
    ? new Intl.DateTimeFormat(locale.value, { day: '2-digit', month: '2-digit' }).format(new Date(value))
    : ''
}

async function submitTask() {
  saving.value = true
  error.value = ''
  try {
    await createTask(name.value, priority.value)
    mode.value = 'active'
    selectedTags.value = []
    name.value = ''
  } catch (cause) {
    error.value = translatedError(t, cause, 'errors.addTask')
  } finally {
    saving.value = false
  }
}

function registerChecklist(id: string, instance: unknown) {
  if (instance) checklistPanels.set(id, instance as { prepareAction: () => Promise<boolean> })
  else checklistPanels.delete(id)
}

async function prepareTaskMutation(id: string): Promise<boolean> {
  if (busyTaskId.value) return false
  if (!await (checklistPanels.get(id)?.prepareAction() ?? Promise.resolve(true))) return false
  return !busyTaskId.value && !anyChecklistBusy.value
}

async function prepareChecklistMutation(task: Task): Promise<boolean> {
  if (busyTaskId.value) return false
  if (editingNameTaskId.value === task.id) {
    await saveTaskName(task)
    if (editingNameTaskId.value) return false
  }
  return !busyTaskId.value
}

async function toggleChecklist(task: Task) {
  if (checklistExpanded.value[task.id]) {
    if (!await (checklistPanels.get(task.id)?.prepareAction() ?? Promise.resolve(true))) return
    checklistExpanded.value[task.id] = false
    void nextTick(() => document.getElementById(`checklist-summary-${task.id}`)?.focus())
  } else {
    checklistExpanded.value[task.id] = true
    if (!task.checklist.length) {
      void nextTick(() => document.getElementById(`checklist-add-${task.id}`)?.focus())
    }
  }
}

async function runTaskAction(taskId: string, action: () => Promise<Task[]>) {
  if (!await prepareTaskMutation(taskId)) return
  busyTaskId.value = taskId
  error.value = ''
  try {
    await action()
    if (!tasks.value.some((task) => task.id === taskId)) {
      delete checklistExpanded.value[taskId]
      void nextTick(() => (document.querySelector<HTMLButtonElement>('.task-name-button')
        ?? document.querySelector<HTMLInputElement>('.new-task input'))?.focus())
    }
  } catch (cause) {
    error.value = translatedError(t, cause, 'errors.updateTask')
  } finally {
    busyTaskId.value = ''
  }
}

function changePriority(taskId: string, value: Priority) {
  return runTaskAction(taskId, () => updateTaskPriority(taskId, value))
}

function visiblePriorityTasks(task: Task) {
  return visibleTasksByPriority.value[task.prioridade]
}

function canReorderTask(task: Task) {
  return (
    mode.value === 'active'
    && dataAvailable.value
    && !busyTaskId.value
    && !anyChecklistBusy.value
    && visiblePriorityTasks(task).length > 1
  )
}

function reorderHandleTitle(task: Task) {
  return canReorderTask(task)
    ? t('task.dragReorder', { priority: t(`priority.${task.prioridade}`) })
    : t('task.dragNeedsPeer')
}

function taskDropPosition(event: DragEvent): 'before' | 'after' {
  const card = event.currentTarget
  if (!(card instanceof HTMLElement)) return 'before'
  const bounds = card.getBoundingClientRect()
  return event.clientY < bounds.top + bounds.height / 2 ? 'before' : 'after'
}

function reorderedTaskIds(
  currentIds: string[],
  sourceId: string,
  targetId: string,
  position: 'before' | 'after',
) {
  const orderedIds = currentIds.filter((taskId) => taskId !== sourceId)
  let targetIndex = orderedIds.indexOf(targetId)
  if (targetIndex < 0) return currentIds
  if (position === 'after') targetIndex += 1
  orderedIds.splice(targetIndex, 0, sourceId)
  return orderedIds
}

function previewTaskMove(sourceId: string, targetId: string, position: 'before' | 'after') {
  const currentIds = dragTaskOrder.value ?? tasks.value.map((task) => task.id)
  const orderedIds = reorderedTaskIds(currentIds, sourceId, targetId, position)
  if (orderedIds.some((taskId, index) => taskId !== currentIds[index])) {
    dragTaskOrder.value = orderedIds
  }
}

function removeTaskDragPreview(preview = dragPreview) {
  preview?.remove()
  if (dragPreview === preview) dragPreview = null
}

function setTaskDragPreview(event: DragEvent) {
  const handle = event.currentTarget
  if (!(handle instanceof HTMLElement) || !event.dataTransfer) return
  const card = handle.closest<HTMLElement>('.task-card')
  if (!card) return

  removeTaskDragPreview()
  const bounds = card.getBoundingClientRect()
  const previewWidth = card.offsetWidth
  const previewHeight = card.offsetHeight
  const preview = card.cloneNode(true) as HTMLElement
  preview.classList.add('task-drag-preview')
  preview.setAttribute('aria-hidden', 'true')
  preview.style.width = `${previewWidth}px`
  preview.style.height = `${previewHeight}px`
  preview.querySelectorAll('[id]').forEach((element) => element.removeAttribute('id'))
  document.body.appendChild(preview)
  dragPreview = preview

  const scaleX = bounds.width > 0 ? previewWidth / bounds.width : 1
  const scaleY = bounds.height > 0 ? previewHeight / bounds.height : 1
  const offsetX = Math.max(0, Math.min(previewWidth, (event.clientX - bounds.left) * scaleX))
  const offsetY = Math.max(0, Math.min(previewHeight, (event.clientY - bounds.top) * scaleY))
  event.dataTransfer.setDragImage(preview, offsetX, offsetY)
  window.setTimeout(() => removeTaskDragPreview(preview), 0)
}

function keepTaskDragCursor(event: DragEvent) {
  if (!draggedTaskId.value) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
}

function cancelTaskDropOutsideList(event: DragEvent) {
  if (!draggedTaskId.value) return
  const target = event.target
  if (target instanceof Element && target.closest('.task-list')) return
  event.preventDefault()
  clearTaskDrag()
}

function addTaskDragWindowListeners() {
  document.addEventListener('dragenter', keepTaskDragCursor, true)
  document.addEventListener('dragover', keepTaskDragCursor, true)
  document.addEventListener('drop', cancelTaskDropOutsideList, true)
}

function removeTaskDragWindowListeners() {
  document.removeEventListener('dragenter', keepTaskDragCursor, true)
  document.removeEventListener('dragover', keepTaskDragCursor, true)
  document.removeEventListener('drop', cancelTaskDropOutsideList, true)
}

function startTaskDrag(task: Task, event: DragEvent) {
  if (!canReorderTask(task)) {
    event.preventDefault()
    return
  }

  dragTaskOrder.value = tasks.value.map((item) => item.id)
  draggedTaskId.value = task.id
  addTaskDragWindowListeners()
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', task.id)
    setTaskDragPreview(event)
  }
}

function dragTaskOver(target: Task, event: DragEvent) {
  const source = tasks.value.find((task) => task.id === draggedTaskId.value)
  if (!source) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  if (source.prioridade !== target.prioridade || source.id === target.id) return

  const position = taskDropPosition(event)
  previewTaskMove(source.id, target.id, position)
}

function dragTaskListOver(event: DragEvent) {
  if (!draggedTaskId.value) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
}

function clearTaskDrag() {
  removeTaskDragWindowListeners()
  removeTaskDragPreview()
  draggedTaskId.value = ''
  if (!preservingDragTaskOrder) dragTaskOrder.value = null
}

async function saveTaskOrder(sourceId: string, orderedIds: string[]) {
  if (!await prepareTaskMutation(sourceId)) return
  const source = tasks.value.find((task) => task.id === sourceId)
  if (!source) return
  const currentIds = tasks.value
    .filter((task) => task.prioridade === source.prioridade)
    .map((task) => task.id)
  if (
    orderedIds.length === currentIds.length
    && orderedIds.every((taskId, index) => taskId === currentIds[index])
  ) return

  busyTaskId.value = sourceId
  error.value = ''
  try {
    await reorderTasks(orderedIds)
  } catch (cause) {
    error.value = translatedError(t, cause, 'errors.reorderTasks')
  } finally {
    busyTaskId.value = ''
  }
}

async function persistTaskOrder(
  sourceId: string,
  targetId: string,
  position: 'before' | 'after',
) {
  const source = tasks.value.find((task) => task.id === sourceId)
  const target = tasks.value.find((task) => task.id === targetId)
  if (!source || !target || source.id === target.id || source.prioridade !== target.prioridade) return
  const currentIds = tasks.value
    .filter((task) => task.prioridade === source.prioridade)
    .map((task) => task.id)
  await saveTaskOrder(sourceId, reorderedTaskIds(currentIds, sourceId, targetId, position))
}

async function commitDraggedTaskOrder() {
  const sourceId = draggedTaskId.value
  const source = tasks.value.find((task) => task.id === sourceId)
  if (!source) return
  const visualOrder = dragTaskOrder.value ?? tasks.value.map((task) => task.id)
  const orderedIds = visualOrder.filter((taskId) =>
    tasks.value.some((task) => task.id === taskId && task.prioridade === source.prioridade),
  )

  preservingDragTaskOrder = true
  clearTaskDrag()
  try {
    await saveTaskOrder(sourceId, orderedIds)
  } finally {
    preservingDragTaskOrder = false
    dragTaskOrder.value = null
  }
}

async function dropTaskOn(target: Task, event: DragEvent) {
  const source = tasks.value.find((task) => task.id === draggedTaskId.value)
  if (!source) return
  event.preventDefault()
  if (source.prioridade !== target.prioridade) return
  if (source.id !== target.id) {
    previewTaskMove(source.id, target.id, taskDropPosition(event))
  }
  await commitDraggedTaskOrder()
}

async function dropCurrentTaskOrder(event: DragEvent) {
  if (!draggedTaskId.value) return
  event.preventDefault()
  await commitDraggedTaskOrder()
}

function moveTaskWithKeyboard(task: Task, direction: -1 | 1) {
  if (!canReorderTask(task)) return
  const visibleGroup = visiblePriorityTasks(task)
  const currentIndex = visibleGroup.findIndex((item) => item.id === task.id)
  const target = visibleGroup[currentIndex + direction]
  if (!target) return
  void persistTaskOrder(task.id, target.id, direction < 0 ? 'before' : 'after')
}

onMounted(async () => {
  if (quickMode || trayMode) return
  clock = window.setInterval(() => {
    now.value = Date.now()
  }, 1000)
  window.addEventListener('tasks-updated', onTasksUpdated)
  window.addEventListener('tasks-refresh-requested', onTasksRefreshRequested)
  window.addEventListener('app-close-requested', onCloseRequested)
  window.addEventListener('keydown', onWindowKeydown)
  try {
    await refreshTasks()
    ;[startupWarnings.value, settings.value] = await Promise.all([getStartupWarnings(), getSettings()])
    applyTheme(settings.value.tema)
    persistedLocale.value = setAppLocale(settings.value.locale)
  } catch (cause) {
    dataAvailable.value = false
    error.value = translatedError(t, cause, 'errors.loadTasks')
  } finally {
    loading.value = false
  }
})

function warningMessage(warning: StartupWarning): string {
  const key = `warnings.${warning.code}`
  return te(key)
    ? t(key, { details: warning.details ?? '' })
    : t('warnings.UNKNOWN')
}

onUnmounted(() => {
  disposed = true
  removeTaskDragWindowListeners()
  window.clearInterval(clock)
  window.removeEventListener('tasks-updated', onTasksUpdated)
  window.removeEventListener('tasks-refresh-requested', onTasksRefreshRequested)
  window.removeEventListener('app-close-requested', onCloseRequested)
  window.removeEventListener('keydown', onWindowKeydown)
})
</script>

<template>
  <QuickAdd v-if="quickMode" />
  <TrayMenu v-else-if="trayMode" />
  <main v-else class="page">
    <header class="header">
      <div>
        <p class="eyebrow">{{ t('app.myTasks') }}</p>
        <h1 class="page-title">
          <span>{{ mode === 'active' ? t('app.today') : t('app.completed') }}</span>
          <time
            v-if="mode === 'active'"
            class="heading-date"
            :datetime="currentDateTime"
          >
            {{ currentDate }}
          </time>
        </h1>
      </div>
      <div class="header-controls">
        <nav class="view-tabs" :aria-label="t('app.view')">
          <button
            class="active-tab"
            type="button"
            :class="{ selected: mode === 'active' }"
            @click="switchMode('active')"
          >
            {{ t('app.active') }} <span>{{ tasks.length }}</span>
          </button>
          <button
            class="completed-tab"
            type="button"
            :class="{ selected: mode === 'completed' }"
            @click="switchMode('completed')"
          >
            {{ t('app.completed') }} <span>{{ completedTasks.length }}</span>
          </button>
        </nav>
        <button class="settings-button" type="button" @click="openSettings">{{ t('app.settings') }}</button>
      </div>
    </header>

    <form v-if="mode === 'active'" class="new-task" @submit.prevent="submitTask">
      <input
        v-model="name"
        maxlength="180"
        :placeholder="t('task.placeholder')"
        :aria-label="t('task.name')"
        autofocus
        :disabled="!dataAvailable"
      />
      <PrioritySelect v-model="priority" :disabled="!dataAvailable" />
      <button type="submit" :disabled="saving || !dataAvailable">
        {{ saving ? t('task.saving') : t('task.add') }}
      </button>
    </form>

    <p v-for="warning in startupWarnings" :key="`${warning.code}:${warning.details ?? ''}`" class="state warning">
      {{ warningMessage(warning) }}
    </p>

    <nav v-if="availableTags.length" class="tag-filters" :aria-label="t('tags.filter')">
      <button
        v-for="tag in availableTags"
        :key="tag"
        type="button"
        :class="{ selected: selectedTags.includes(tag) }"
        :style="filterTagStyle(tag)"
        @click="toggleTag(tag)"
      >
        {{ selectedTags.includes(tag) ? '✓ ' : '' }}#{{ tag }}
      </button>
    </nav>

    <p v-if="loading" class="state">{{ t('task.loading') }}</p>
    <p v-else-if="error" class="state error">{{ error }}</p>
    <p v-else-if="sourceTasks.length === 0" class="state">
      {{ mode === 'active' ? t('task.emptyActive') : t('task.emptyCompleted') }}
    </p>
    <p v-else-if="visibleTasks.length === 0" class="state">{{ t('task.emptyFiltered') }}</p>

    <TransitionGroup
      v-else
      name="task-reorder"
      tag="section"
      class="task-list"
      @dragover="dragTaskListOver"
      @drop="dropCurrentTaskOrder"
    >
      <div key="task-list-header" class="task-list-header" aria-hidden="true">
        <span class="task-column-heading">{{ t('task.column') }}</span>
        <span>{{ t('priority.label') }}</span>
        <span>{{ mode === 'active' ? t('task.addedOn') : t('task.completedOn') }}</span>
      </div>
      <article
        v-for="task in visibleTasks"
        :key="task.id"
        class="task-card"
        :data-task-id="task.id"
        tabindex="-1"
        :class="{
          running: task.cronometro_iniciado_em,
          completed: mode === 'completed',
          dragging: draggedTaskId === task.id,
        }"
        @dragover.stop="dragTaskOver(task, $event)"
        @drop.stop="dropTaskOn(task, $event)"
      >
        <button
          v-if="mode === 'active'"
          class="drag-handle"
          type="button"
          :disabled="!canReorderTask(task)"
          :draggable="canReorderTask(task)"
          :aria-label="reorderHandleTitle(task)"
          aria-keyshortcuts="ArrowUp ArrowDown"
          :title="reorderHandleTitle(task)"
          @dragstart="startTaskDrag(task, $event)"
          @dragend="clearTaskDrag"
          @keydown.up.prevent="moveTaskWithKeyboard(task, -1)"
          @keydown.down.prevent="moveTaskWithKeyboard(task, 1)"
        >
          <span aria-hidden="true">⠿</span>
        </button>
        <span v-else class="drag-handle-placeholder" aria-hidden="true"></span>
        <span class="priority-rail" :data-priority="task.prioridade" aria-hidden="true"></span>
        <div class="task-timer">
          <span class="timer">{{ formatTime(task) }}</span>
        </div>
        <div class="task-copy">
          <div v-if="editingNameTaskId === task.id" class="task-name-editor">
            <input
              v-model="editedName"
              class="task-name-input"
              maxlength="120"
              :aria-label="t('task.editName')"
              :aria-invalid="Boolean(nameEditorError)"
              :disabled="busyTaskId === task.id"
              @keydown.enter.prevent="saveTaskName(task)"
              @keydown.esc.stop.prevent="cancelNameEdit"
              @blur="saveTaskName(task)"
            />
            <p v-if="nameEditorError" class="name-editor-error" role="alert">
              {{ nameEditorError }}
            </p>
          </div>
          <h2 v-else>
            <button
              v-if="mode === 'active'"
              class="task-name-button"
              type="button"
              :aria-label="t('task.editNameFor', { name: task.nome })"
              :title="t('task.clickToEdit')"
              @click="startNameEdit(task)"
            >
              {{ task.nome }}
            </button>
            <template v-else>{{ task.nome }}</template>
          </h2>
          <div v-if="task.tags.length" class="tags">
            <button
              v-for="tag in task.tags"
              :key="tag"
              type="button"
              :disabled="mode === 'completed'"
              :style="tagStyle(task, tag)"
              @click="openTagEditor(task)"
            >
              #{{ tag }}
            </button>
          </div>
          <button
            v-if="mode === 'active' || task.checklist.length"
            :id="`checklist-summary-${task.id}`"
            type="button"
            class="checklist-summary"
            :aria-expanded="Boolean(checklistExpanded[task.id])"
            :aria-controls="`checklist-panel-${task.id}`"
            :aria-label="t(checklistExpanded[task.id] ? 'checklist.hideFor' : 'checklist.showFor', {
              name: task.nome, done: task.checklist.filter((item) => item.concluido).length,
              total: task.checklist.length,
            })"
            @click="toggleChecklist(task)"
          >
            <span aria-hidden="true">{{ checklistExpanded[task.id] ? '⌄' : task.checklist.length ? '›' : '+' }}</span>
            {{ task.checklist.length || checklistExpanded[task.id]
              ? t('checklist.summary', { done: task.checklist.filter((item) => item.concluido).length, total: task.checklist.length })
              : t('checklist.add') }}
          </button>
        </div>

        <div class="task-priority">
          <PrioritySelect
            v-if="mode === 'active'"
            compact
            :model-value="task.prioridade"
            :disabled="busyTaskId === task.id"
            @update:model-value="changePriority(task.id, $event)"
          />
          <span v-else class="priority" :data-priority="task.prioridade">{{ t(`priority.${task.prioridade}`) }}</span>
        </div>

        <time
          class="task-date"
          :datetime="mode === 'active' ? task.adicionada_em : (task.completedAt ?? undefined)"
        >
          {{ formatDate(mode === 'active' ? task.adicionada_em : task.completedAt) }}
        </time>

        <div v-if="mode === 'active'" class="task-actions">
          <button
            class="timer-button"
            type="button"
            :disabled="busyTaskId === task.id"
            :aria-label="task.cronometro_iniciado_em ? t('actions.pauseTimer') : t('actions.startTimer')"
            :title="task.cronometro_iniciado_em ? t('actions.pauseTimer') : t('actions.startTimer')"
            @click="runTaskAction(task.id, () => toggleTaskTimer(task.id))"
          >
            <img
              :src="task.cronometro_iniciado_em ? pauseIcon : playIcon"
              alt=""
              aria-hidden="true"
            />
          </button>
          <button
            v-if="task.cronometro_iniciado_em"
            class="complete"
            type="button"
            :disabled="busyTaskId === task.id"
            :aria-label="t('actions.completeTask')"
            :title="t('actions.completeTask')"
            @click="runTaskAction(task.id, () => completeTask(task.id))"
          >
            <img :src="completeIcon" alt="" aria-hidden="true" />
          </button>
          <button
            class="delete"
            type="button"
            :disabled="busyTaskId === task.id"
            :aria-label="t('actions.deleteTask')"
            :title="t('actions.deleteTask')"
            @click="runTaskAction(task.id, () => deleteTask(task.id))"
          >
            <img :src="deleteIcon" alt="" aria-hidden="true" />
          </button>
        </div>
        <span v-else class="completed-label">{{ t('task.completedLabel') }}</span>
        <TaskChecklist
          :ref="(instance) => registerChecklist(task.id, instance)"
          :task="task"
          :expanded="Boolean(checklistExpanded[task.id])"
          :readonly="mode === 'completed'"
          :disabled="Boolean(busyTaskId) || !dataAvailable"
          :before-mutation="() => prepareChecklistMutation(task)"
          @busy="checklistBusy[task.id] = $event"
          @collapse="toggleChecklist(task)"
        />
      </article>
    </TransitionGroup>

    <div
      v-if="editingTask"
      class="modal-backdrop"
      role="presentation"
      @click.self="closeTagEditor"
    >
      <form
        class="tag-editor"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tag-editor-title"
        @submit.prevent="saveTags"
        @keydown.esc="closeTagEditor"
      >
        <p class="eyebrow">{{ t('tags.edit') }}</p>
        <h2 id="tag-editor-title">{{ editingTask.nome }}</h2>
        <input
          v-model="editedTags"
          autofocus
          :placeholder="t('tags.placeholder')"
          :aria-label="t('tags.label')"
          :aria-invalid="!editedTagsAreValid"
          :disabled="busyTaskId === editingTask.id"
        />
        <p class="tag-hint">{{ t('tags.hint') }}</p>
        <p v-if="!editedTagsAreValid" class="editor-error" role="alert">
          {{ t('tags.formatError') }}
        </p>
        <p v-else-if="editorError" class="editor-error" role="alert">{{ editorError }}</p>

        <section v-if="editorTags.length" class="tag-color-options" aria-labelledby="tag-colors-title">
          <p id="tag-colors-title" class="tag-color-title">{{ t('tags.colors') }}</p>
          <div v-for="tag in editorTags" :key="tag" class="tag-color-row">
            <span class="edited-tag-preview" :style="editedTagStyle(tag)">#{{ tag }}</span>
            <input
              class="tag-color-picker"
              type="color"
              :value="editedTagColors[tag]"
              :aria-label="t('tags.changeColor', { tag })"
              :title="t('tags.changeColorTitle', { tag })"
              :disabled="busyTaskId === editingTask.id"
              @input="updateEditedTagColor(tag, $event)"
            />
          </div>
        </section>
        <p v-else-if="editedTagsAreValid" class="tag-color-empty">
          {{ t('tags.emptyColors') }}
        </p>

        <div class="editor-actions">
          <button type="button" :disabled="busyTaskId === editingTask.id" @click="closeTagEditor">{{ t('actions.cancel') }}</button>
          <button type="submit" :disabled="busyTaskId === editingTask.id || !editedTagsAreValid">
            {{ busyTaskId === editingTask.id ? t('task.saving') : t('tags.save') }}
          </button>
        </div>
      </form>
    </div>

    <div
      v-if="settingsOpen"
      class="modal-backdrop"
      role="presentation"
      @click.self="closeSettings"
    >
      <form class="settings-panel" role="dialog" aria-modal="true" @submit.prevent="submitSettings" @keydown.esc="closeSettings">
        <p class="eyebrow">{{ t('settings.title') }}</p>
        <div class="theme-setting">
          <label for="interface-theme">{{ t('settings.interfaceTheme') }}</label>
          <select id="interface-theme" v-model="settings.tema">
            <option value="dark">{{ t('settings.dark') }}</option>
            <option value="light">{{ t('settings.light') }}</option>
          </select>
        </div>
        <div class="theme-setting">
          <label for="interface-language">{{ t('settings.language') }}</label>
          <select id="interface-language" v-model="settings.locale" @change="setAppLocale(settings.locale)">
            <option v-for="item in supportedLocales" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </div>
        <h2>{{ t('settings.hotkeyTitle') }}</h2>
        <div class="modifier-list">
          <label><input v-model="settings.ctrl" type="checkbox" /> Ctrl</label>
          <label><input v-model="settings.alt" type="checkbox" /> Alt</label>
          <label><input v-model="settings.shift" type="checkbox" /> Shift</label>
          <select v-model="settings.tecla" :aria-label="t('settings.primaryKey')">
            <option v-for="key in hotkeyKeys" :key="key" :value="key">{{ key }}</option>
          </select>
        </div>
        <p class="tag-hint">{{ t('settings.currentShortcut', { shortcut: settings.description ?? 'Ctrl + Alt + T' }) }}</p>
        <p v-if="settingsError" class="editor-error">{{ settingsError }}</p>
        <div class="editor-actions settings-actions">
          <button type="button" @click="restoreDefaultHotkey">{{ t('settings.restoreDefault') }}</button>
          <button type="button" @click="closeSettings">{{ t('actions.cancel') }}</button>
          <button type="submit" :disabled="settingsSaving">
            {{ settingsSaving ? t('task.saving') : t('settings.save') }}
          </button>
        </div>
      </form>
    </div>

    <div
      v-if="closeDialogOpen"
      class="modal-backdrop"
      role="presentation"
      @keydown.esc="closeDialogOpen = false"
    >
      <section class="close-panel" role="dialog" aria-modal="true">
        <p class="eyebrow">{{ t('close.title') }}</p>
        <h2>{{ t('close.question') }}</h2>
        <p class="tag-hint">{{ t('close.hint') }}</p>
        <div class="close-actions">
          <button type="button" class="danger" @click="exitApp">{{ t('close.closeApp') }}</button>
          <button type="button" class="primary" @click="keepInBackground">{{ t('close.background') }}</button>
          <button type="button" @click="closeDialogOpen = false">{{ t('actions.cancel') }}</button>
        </div>
      </section>
    </div>
  </main>
</template>

