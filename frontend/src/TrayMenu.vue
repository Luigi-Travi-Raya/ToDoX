<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import completeIcon from '../../../assets/icons/complete.svg'
import pauseIcon from '../../../assets/icons/pause.svg'
import playIcon from '../../../assets/icons/play.svg'
import {
  closeTrayMenu,
  completeTask,
  exitApp,
  getSettings,
  getCurrentTaskUpdate,
  listTasks,
  openQuickAdd,
  showMainWindow,
  toggleTaskTimer,
  type HotkeySettings,
  type Priority,
  type Task,
  type TaskUpdate,
} from './api'
import { applyTheme } from './theme'
import { setAppLocale } from './i18n'
import { translatedError } from './i18n/errors'

const { t } = useI18n()
const tasks = ref<Task[]>([])
const settings = ref<HotkeySettings>({ ctrl: true, alt: true, shift: false, tecla: 'T', tema: 'dark', locale: 'en' })
const loading = ref(true)
const error = ref('')
const busyTaskId = ref('')
const busyAction = ref('')
const now = ref(Date.now())
let clock: number | undefined
let taskGeneration = 0
let refreshPending: Promise<void> | null = null
let themeRefreshPending: Promise<void> | null = null
let disposed = false

const startedTasks = computed(() =>
  tasks.value
    .filter((task) => task.atividade_iniciada)
    .sort((first, second) => {
      const runningDifference = Number(Boolean(second.cronometro_iniciado_em)) - Number(Boolean(first.cronometro_iniciado_em))
      // Array#sort is stable: tasks in the same state keep the priority/date
      // order supplied by list_tasks.
      return runningDifference
    }),
)

const shortcut = computed(() => {
  if (settings.value.description) return settings.value.description
  const keys = [
    settings.value.ctrl && 'Ctrl',
    settings.value.alt && 'Alt',
    settings.value.shift && 'Shift',
    settings.value.tecla,
  ].filter(Boolean)
  return keys.join(' + ')
})

function priorityColor(priority: Priority): string {
  if (priority === 'urgent') return '#f04438'
  if (priority === 'high') return '#ff8a3d'
  if (priority === 'low') return '#48c78e'
  if (priority === 'very_low') return '#38bdf8'
  return '#f4d35e'
}

function taskSeconds(task: Task): number {
  let seconds = task.tempo_acumulado_segundos
  if (task.cronometro_iniciado_em) {
    const startedAt = Date.parse(task.cronometro_iniciado_em)
    if (Number.isFinite(startedAt)) seconds += Math.max(0, Math.floor((now.value - startedAt) / 1000))
  }
  return Math.max(0, Math.floor(seconds))
}

function formatTime(task: Task): string {
  const totalSeconds = taskSeconds(task)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, '0')).join(':')
}

function refresh(): Promise<void> {
  if (refreshPending !== null) return refreshPending
  const generation = taskGeneration
  refreshPending = (async () => {
    try {
      const updatedTasks = await listTasks()
      if (disposed || generation !== taskGeneration) return
      tasks.value = updatedTasks
      error.value = ''
    } catch (cause) {
      if (!disposed && generation === taskGeneration) {
        error.value = translatedError(t, cause, 'errors.loadActivities')
      }
    } finally {
      loading.value = false
      refreshPending = null
    }
  })()
  return refreshPending
}

function refreshTheme(): Promise<void> {
  if (themeRefreshPending !== null) return themeRefreshPending
  themeRefreshPending = (async () => {
    try {
      const updatedSettings = await getSettings()
      if (disposed) return
      settings.value = updatedSettings
      applyTheme(settings.value.tema)
      setAppLocale(settings.value.locale)
    } catch {
      if (disposed) return
      applyTheme('dark')
      setAppLocale('en')
    } finally {
      themeRefreshPending = null
    }
  })()
  return themeRefreshPending
}

function applyTaskUpdate(update: TaskUpdate): void {
  taskGeneration += 1
  tasks.value = update.tasks
  loading.value = false
  error.value = ''
}

function onTasksUpdated(event: CustomEvent<TaskUpdate>): void {
  applyTaskUpdate(event.detail)
}

function onTrayShown(): void {
  now.value = Date.now()
  void Promise.all([refresh(), refreshTheme()])
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') void dismiss()
}

async function dismiss(): Promise<void> {
  try {
    await closeTrayMenu()
  } catch (cause) {
    error.value = translatedError(t, cause, 'errors.closeTray')
  }
}

async function runTaskAction(task: Task, action: (taskId: string) => Promise<Task[]>): Promise<void> {
  if (busyTaskId.value || busyAction.value) return
  busyTaskId.value = task.id
  error.value = ''
  try {
    await action(task.id)
  } catch (cause) {
    error.value = translatedError(t, cause, 'errors.updateActivity')
  } finally {
    busyTaskId.value = ''
  }
}

async function runMenuAction(name: string, action: () => Promise<void>, closeAfter = true): Promise<void> {
  if (busyTaskId.value || busyAction.value) return
  busyAction.value = name
  error.value = ''
  try {
    await action()
    if (closeAfter) await closeTrayMenu()
  } catch (cause) {
    error.value = translatedError(t, cause, 'errors.menuAction')
  } finally {
    busyAction.value = ''
  }
}

onMounted(async () => {
  document.documentElement.classList.add('tray-menu-document')
  document.body.classList.add('tray-menu-body')
  clock = window.setInterval(() => {
    now.value = Date.now()
  }, 1000)
  window.addEventListener('tasks-updated', onTasksUpdated)
  window.addEventListener('tray-menu-shown', onTrayShown)
  window.addEventListener('keydown', onKeydown)
  const currentUpdate = getCurrentTaskUpdate()
  if (currentUpdate !== null) applyTaskUpdate(currentUpdate)
  await Promise.all([refresh(), refreshTheme()])
})

onUnmounted(() => {
  disposed = true
  document.documentElement.classList.remove('tray-menu-document')
  document.body.classList.remove('tray-menu-body')
  window.clearInterval(clock)
  window.removeEventListener('tasks-updated', onTasksUpdated)
  window.removeEventListener('tray-menu-shown', onTrayShown)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <main
    class="tray-menu"
    :aria-label="t('tray.menu')"
    :aria-busy="Boolean(busyTaskId || busyAction)"
  >
    <header class="tray-header">
      <strong>ToDoX</strong>
      <button class="close-menu" type="button" :aria-label="t('tray.closeMenu')" :title="t('tray.close')" @click="dismiss">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="m7 7 10 10M17 7 7 17" />
        </svg>
      </button>
    </header>

    <section class="activity-section" aria-labelledby="started-activities-title">
      <h1 id="started-activities-title">
        {{ t('tray.heading') }}
        <span v-if="!loading">{{ startedTasks.length }}</span>
      </h1>

      <div class="activity-scroll">
        <div v-if="loading" class="tray-status" aria-live="polite">{{ t('tray.loading') }}</div>

        <div v-else-if="error && tasks.length === 0" class="tray-status error" role="alert">
          {{ error }}
        </div>

        <div v-else-if="startedTasks.length === 0" class="tray-status empty">
          {{ t('tray.empty') }}
        </div>

        <article
          v-for="task in startedTasks"
          v-else
          :key="task.id"
          class="activity-card"
          :class="{ running: task.cronometro_iniciado_em }"
        >
          <span
            class="priority-dot"
            :style="{ '--priority-dot': priorityColor(task.prioridade) }"
            :title="t('tray.priority', { priority: t(`priority.${task.prioridade}`) })"
            role="img"
            :aria-label="t('tray.priority', { priority: t(`priority.${task.prioridade}`) })"
          ></span>

          <div class="activity-copy">
            <strong :title="task.nome">{{ task.nome }}</strong>
            <div class="activity-meta">
              <time :aria-label="t('tray.duration', { time: formatTime(task) })">{{ formatTime(task) }}</time>
              <span :class="{ running: task.cronometro_iniciado_em }">
                {{ task.cronometro_iniciado_em ? t('tray.running') : t('tray.paused') }}
              </span>
            </div>
          </div>

          <div class="activity-controls">
            <button
              class="icon-button timer-control"
              type="button"
              :disabled="Boolean(busyTaskId || busyAction)"
              :aria-label="task.cronometro_iniciado_em ? t('tray.pauseTask', { name: task.nome }) : t('tray.continueTask', { name: task.nome })"
              :title="task.cronometro_iniciado_em ? t('tray.pauseActivity') : t('tray.continueActivity')"
              @click="runTaskAction(task, toggleTaskTimer)"
            >
              <img :src="task.cronometro_iniciado_em ? pauseIcon : playIcon" alt="" />
            </button>
            <button
              class="icon-button complete-control"
              type="button"
              :disabled="Boolean(busyTaskId || busyAction)"
              :aria-label="t('tray.completeTask', { name: task.nome })"
              :title="t('tray.completeActivity')"
              @click="runTaskAction(task, completeTask)"
            >
              <img :src="completeIcon" alt="" />
            </button>
          </div>
        </article>
      </div>

      <p v-if="error && tasks.length > 0" class="tray-error" role="alert">{{ error }}</p>
    </section>

    <nav class="tray-actions" :aria-label="t('tray.quickActions')">
      <button
        type="button"
        :disabled="Boolean(busyTaskId || busyAction)"
        @click="runMenuAction('quick-add', openQuickAdd)"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 5v14M5 12h14" />
        </svg>
        <span>{{ t('tray.newTask') }}</span>
        <kbd v-if="shortcut">{{ shortcut }}</kbd>
      </button>

      <button
        type="button"
        :disabled="Boolean(busyTaskId || busyAction)"
        @click="runMenuAction('main', showMainWindow)"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M8 6h11M8 12h11M8 18h11" />
          <path d="m3.5 6 .8.8L6 5.1M3.5 12l.8.8L6 11.1M3.5 18l.8.8 1.7-1.7" />
        </svg>
        <span>{{ t('tray.openList') }}</span>
      </button>

      <div class="action-divider" role="separator"></div>

      <button
        class="exit-action"
        type="button"
        :disabled="Boolean(busyTaskId || busyAction)"
        @click="runMenuAction('exit', exitApp, false)"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M10 5H5v14h5M14 8l4 4-4 4M9 12h9" />
        </svg>
        <span>{{ t('tray.exit') }}</span>
      </button>
    </nav>
  </main>
</template>

<style scoped>
:global(html.tray-menu-document),
:global(body.tray-menu-body) {
  min-width: 0;
  min-height: 100%;
  overflow: hidden;
  background: transparent;
}

:global(body.tray-menu-body) {
  zoom: 1;
}

.tray-menu {
  --tray-bg: #101522;
  --tray-surface: #171e2d;
  --tray-surface-hover: #20293b;
  --tray-border: #2a3447;
  --tray-text: #f4f7fb;
  --tray-muted: #94a0b4;
  --tray-subtle: #758197;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--tray-border);
  border-radius: 15px;
  color: var(--tray-text);
  background: var(--tray-bg);
  box-shadow: 0 16px 42px rgb(0 0 0 / 34%);
}

.tray-header {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 9px;
  height: 48px;
  padding: 0 15px;
  border-bottom: 1px solid var(--tray-border);
}

.tray-header strong {
  font-size: 15px;
  font-weight: 750;
  letter-spacing: -0.01em;
}

.close-menu {
  display: grid;
  width: 28px;
  height: 28px;
  margin-left: auto;
  padding: 0;
  place-items: center;
  border: 0;
  border-radius: 7px;
  color: var(--tray-muted);
  background: transparent;
}

.close-menu:hover {
  color: var(--tray-text);
  background: var(--tray-surface-hover);
  box-shadow: none;
  filter: none;
  transform: none;
}

.close-menu svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-width: 1.8;
}

.activity-section {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
  flex-direction: column;
  padding: 10px 10px 7px;
}

.activity-section h1 {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  margin: 0 5px 7px;
  color: var(--tray-muted);
  font-size: 10px;
  font-weight: 750;
  letter-spacing: 0.1em;
  line-height: 1.2;
  text-transform: uppercase;
}

.activity-section h1 span {
  display: grid;
  min-width: 17px;
  height: 17px;
  place-items: center;
  border-radius: 999px;
  color: #c5bdfc;
  font-size: 9px;
  letter-spacing: 0;
  background: #302a58;
}

.activity-scroll {
  display: grid;
  flex: 1 1 auto;
  align-content: start;
  gap: 6px;
  grid-auto-rows: max-content;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-color: #39455a transparent;
  scrollbar-width: thin;
}

.activity-scroll::-webkit-scrollbar {
  width: 5px;
}

.activity-scroll::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: #39455a;
}

.activity-card {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  min-height: 58px;
  padding: 9px 9px 9px 11px;
  border: 1px solid var(--tray-border);
  border-radius: 11px;
  background: var(--tray-surface);
}

.activity-card.running {
  border-color: color-mix(in srgb, #32d583 35%, var(--tray-border));
}

.priority-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--priority-dot);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--priority-dot) 16%, transparent);
}

.activity-copy {
  min-width: 0;
}

.activity-copy strong {
  display: block;
  overflow: hidden;
  margin-bottom: 4px;
  font-size: 12.5px;
  font-weight: 650;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-meta {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}

.activity-meta time {
  color: var(--tray-subtle);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.04em;
  line-height: 1.2;
}

.activity-meta span {
  overflow: hidden;
  color: #a79af8;
  font-size: 10px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-meta span.running {
  color: #6ce9a6;
}

.activity-controls {
  display: flex;
  gap: 5px;
}

.icon-button {
  display: grid;
  width: 30px;
  height: 30px;
  padding: 0;
  place-items: center;
  border: 1px solid var(--tray-border);
  border-radius: 8px;
  color: var(--tray-muted);
  background: #111827;
}

.icon-button img {
  width: 16px;
  height: 16px;
}

.icon-button.timer-control {
  border-color: #30455c;
  background: #162437;
}

.icon-button.complete-control {
  border-color: #27523f;
  background: #142b23;
}

.icon-button:disabled,
.tray-actions button:disabled {
  cursor: wait;
  opacity: 0.5;
}

.tray-status {
  display: grid;
  min-height: 34px;
  place-items: center;
  padding: 9px;
  border: 1px dashed var(--tray-border);
  border-radius: 10px;
  color: var(--tray-muted);
  font-size: 11.5px;
  text-align: center;
}

.tray-status.empty {
  color: var(--tray-subtle);
}

.tray-status.error {
  border-color: rgb(240 68 56 / 45%);
  color: #ff8c95;
}

.tray-error {
  flex: 0 0 auto;
  overflow: hidden;
  margin: 7px 4px 0;
  color: #ff8c95;
  font-size: 10.5px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tray-actions {
  flex: 0 0 auto;
  padding: 5px 8px 7px;
  border-top: 1px solid var(--tray-border);
}

.tray-actions button {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  width: 100%;
  min-height: 36px;
  padding: 0 9px;
  border: 0;
  border-radius: 8px;
  color: var(--tray-text);
  background: transparent;
  text-align: left;
}

.tray-actions button:hover {
  background: var(--tray-surface-hover);
  box-shadow: none;
  filter: none;
  transform: none;
}

.tray-actions svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}

.tray-actions span {
  font-size: 12.5px;
  font-weight: 560;
}

.tray-actions kbd {
  color: var(--tray-subtle);
  font-family: inherit;
  font-size: 9.5px;
  font-weight: 500;
  white-space: nowrap;
}

.action-divider {
  height: 1px;
  margin: 5px 7px;
  background: var(--tray-border);
}

.tray-actions .exit-action {
  color: #fda4aa;
}

:global(:root[data-theme='light']) .tray-menu {
  --tray-bg: #ffffff;
  --tray-surface: #f6f8fb;
  --tray-surface-hover: #eef1f6;
  --tray-border: #dce2ea;
  --tray-text: #202a3a;
  --tray-muted: #647087;
  --tray-subtle: #7f8a9d;
  box-shadow: 0 16px 42px rgb(51 65 85 / 22%);
}

:global(:root[data-theme='light']) .activity-section h1 span {
  color: #5c48c5;
  background: #ece9ff;
}

:global(:root[data-theme='light']) .activity-card.running {
  border-color: #a6dfbf;
  background: #f1faf5;
}

:global(:root[data-theme='light']) .activity-meta span {
  color: #6651dc;
}

:global(:root[data-theme='light']) .activity-meta span.running {
  color: #18794e;
}

:global(:root[data-theme='light']) .icon-button {
  background: #ffffff;
}

:global(:root[data-theme='light']) .icon-button.timer-control {
  border-color: #cbd7e5;
  background: #edf3f9;
}

:global(:root[data-theme='light']) .icon-button.complete-control {
  border-color: #b9dec9;
  background: #eaf7ef;
}

:global(:root[data-theme='light']) .tray-actions .exit-action {
  color: #c83d48;
}

:global(:root[data-theme='light']) .tray-status.error {
  color: #c52c3a;
}

@media (max-width: 300px) {
  .tray-header {
    padding-inline: 11px;
  }

  .activity-card {
    gap: 7px;
    padding-inline: 8px;
  }

  .tray-actions kbd {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .tray-menu button {
    transition: none;
  }
}
</style>
