<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import deleteIcon from '../../../assets/icons/delete.svg'
import {
  addChecklistItem, updateChecklistItem, setChecklistItemCompleted,
  deleteChecklistItem, type Task, type ChecklistItem,
} from './api'
import { translatedError } from './i18n/errors'

const props = defineProps<{
  task: Task
  expanded: boolean
  readonly: boolean
  disabled: boolean
  beforeMutation: () => Promise<boolean>
}>()
const emit = defineEmits<{
  busy: [value: boolean]
  collapse: []
}>()
const { t } = useI18n()
const draft = ref('')
const editingId = ref('')
const editedName = ref('')
const error = ref('')
const errorField = ref('')
const busy = ref(false)
const announcement = ref('')
const panel = ref<HTMLElement | null>(null)
let pending: Promise<boolean> | null = null
const items = computed(() => props.task.checklist)
const unavailable = computed(() => props.disabled || props.readonly || busy.value)
const fieldId = computed(() => `checklist-add-${props.task.id}`)
const errorId = computed(() => `checklist-error-${props.task.id}`)

function focusElement(id: string) {
  void nextTick(() => document.getElementById(id)?.focus())
}

function normalize(value: string) { return value.replace(/[\r\n]+/g, ' ').trim() }
function validate(value: string, field: string): string | null {
  const name = normalize(value)
  const key = !name ? 'CHECKLIST_NAME_REQUIRED' : Array.from(name).length > 120 ? 'CHECKLIST_NAME_TOO_LONG' : ''
  if (key) {
    error.value = t(`errors.${key}`)
    errorField.value = field
    focusElement(field === 'add' ? fieldId.value : `checklist-edit-${field}`)
    return null
  }
  return name
}

function mutate(action: () => Promise<Task[]>, after: () => void): Promise<boolean> {
  if (pending) return pending
  if (unavailable.value) return Promise.resolve(false)
  pending = (async () => {
    if (!await props.beforeMutation()) return false
    busy.value = true
    emit('busy', true)
    error.value = ''
    errorField.value = ''
    try {
      const tasks = await action()
      after()
      const updated = tasks.find((task) => task.id === props.task.id)
      if (updated) announcement.value = t('checklist.updated', {
        name: updated.nome, done: updated.checklist.filter((item) => item.concluido).length,
        total: updated.checklist.length,
      })
      return true
    } catch (cause) {
      error.value = translatedError(t, cause, 'errors.updateChecklist')
      return false
    } finally {
      busy.value = false
      emit('busy', false)
    }
  })().finally(() => { pending = null })
  return pending
}

function cancelEdit() {
  const id = editingId.value
  editingId.value = ''
  error.value = ''
  errorField.value = ''
  focusElement(`checklist-text-${id}`)
}

async function saveEdit(restoreFocus = false): Promise<boolean> {
  if (pending) return pending
  const id = editingId.value
  if (!id) return true
  const name = validate(editedName.value, id)
  if (name === null) return false
  const previous = items.value.find((item) => item.id === id)
  if (!previous) {
    cancelEdit()
    return true
  }
  if (name === previous.nome) {
    editingId.value = ''
    error.value = ''
    if (restoreFocus) focusElement(`checklist-text-${id}`)
    return true
  }
  return mutate(() => updateChecklistItem(props.task.id, id, name), () => {
    editingId.value = ''
    if (restoreFocus) focusElement(`checklist-text-${id}`)
  })
}

async function prepareAction(): Promise<boolean> {
  if (pending && !await pending) return false
  return editingId.value ? saveEdit() : true
}

async function startEdit(item: ChecklistItem) {
  if (props.disabled || props.readonly || !await prepareAction() || unavailable.value) return
  editingId.value = item.id
  editedName.value = item.nome
  error.value = ''
  focusElement(`checklist-edit-${item.id}`)
}

async function addItem() {
  if (props.disabled || props.readonly || !await prepareAction() || unavailable.value) return
  const name = validate(draft.value, 'add')
  if (name === null) return
  await mutate(() => addChecklistItem(props.task.id, name), () => {
    draft.value = ''
    focusElement(fieldId.value)
  })
}

async function markItem(item: ChecklistItem, event: Event) {
  const checkbox = event.target as HTMLInputElement
  const desired = checkbox.checked
  checkbox.checked = item.concluido
  if (props.disabled || props.readonly || !await prepareAction() || unavailable.value) return
  await mutate(() => setChecklistItemCompleted(props.task.id, item.id, desired), () => {
    focusElement(`checklist-check-${item.id}`)
  })
}

async function removeItem(item: ChecklistItem) {
  if (props.disabled || props.readonly || !await prepareAction() || unavailable.value) return
  const position = items.value.findIndex((current) => current.id === item.id)
  if (position < 0) return
  const focusId = items.value[position + 1]?.id ?? items.value[position - 1]?.id
  await mutate(() => deleteChecklistItem(props.task.id, item.id), () => {
    focusElement(focusId ? `checklist-check-${focusId}` : fieldId.value)
  })
}

function escape(event: KeyboardEvent) {
  event.stopPropagation()
  event.preventDefault()
  if (busy.value) return
  if (editingId.value) cancelEdit()
  else if (event.target === document.getElementById(fieldId.value) && draft.value) {
    draft.value = ''
    error.value = ''
    document.getElementById(`checklist-summary-${props.task.id}`)?.focus()
  } else emit('collapse')
}

watch(() => props.readonly, (value) => {
  if (value) { editingId.value = ''; draft.value = '' }
})
watch(items, (value) => {
  if (editingId.value && !value.some((item) => item.id === editingId.value)) {
    editingId.value = ''
    focusElement(fieldId.value)
  }
})

defineExpose({ prepareAction })
</script>

<template>
  <section
    v-show="expanded"
    :id="`checklist-panel-${task.id}`"
    ref="panel"
    class="task-checklist"
    :aria-label="t('checklist.panelFor', { name: task.nome })"
    :aria-busy="busy"
    :aria-describedby="readonly ? `checklist-readonly-${task.id}` : undefined"
    @keydown.esc="escape"
    @dragover.stop
    @drop.stop
  >
    <p v-if="readonly" :id="`checklist-readonly-${task.id}`" class="checklist-hint">{{ t('checklist.readOnly') }}</p>
    <p v-if="!items.length" class="checklist-hint">{{ t('checklist.empty') }}</p>
    <ul v-else class="checklist-items">
      <li v-for="item in items" :key="item.id" class="checklist-row" :class="{ 'is-checked': item.concluido }">
        <label class="checklist-checkbox-target">
          <input
            :id="`checklist-check-${item.id}`"
            type="checkbox"
            :checked="item.concluido"
            :disabled="readonly"
            :aria-disabled="unavailable"
            :aria-label="t('checklist.markItem', { name: item.nome })"
            @click="(disabled || readonly) && $event.preventDefault()"
            @change="markItem(item, $event)"
          />
        </label>
        <input
          v-if="editingId === item.id && !readonly"
          :id="`checklist-edit-${item.id}`"
          v-model="editedName"
          class="checklist-input"
          :aria-label="t('checklist.editItem', { name: item.nome })"
          :aria-invalid="errorField === item.id"
          :aria-describedby="errorField === item.id ? errorId : undefined"
          :readonly="busy"
          @keydown.enter="!$event.isComposing && ($event.preventDefault(), saveEdit(true))"
          @blur="saveEdit()"
        />
        <span v-else-if="readonly" class="checklist-item-text">{{ item.nome }}</span>
        <button
          v-else
          :id="`checklist-text-${item.id}`"
          type="button"
          class="checklist-item-text"
          :aria-label="t('checklist.editItem', { name: item.nome })"
          :aria-disabled="unavailable"
          @click="startEdit(item)"
        >{{ item.nome }}</button>
        <button
          v-if="!readonly"
          type="button"
          class="checklist-delete"
          :aria-label="t('checklist.deleteItem', { name: item.nome })"
          :title="t('checklist.deleteItem', { name: item.nome })"
          :aria-disabled="unavailable"
          @click="removeItem(item)"
        ><img :src="deleteIcon" alt="" aria-hidden="true" /></button>
      </li>
    </ul>
    <form v-if="!readonly" class="checklist-composer" @submit.prevent="addItem">
      <input
        :id="fieldId"
        v-model="draft"
        class="checklist-input"
        :placeholder="t('checklist.placeholder')"
        :aria-label="t('checklist.addItem')"
        :aria-invalid="errorField === 'add'"
        :aria-describedby="errorField === 'add' ? errorId : undefined"
        :readonly="unavailable"
        @keydown.enter="($event.isComposing || $event.keyCode === 229) && $event.preventDefault()"
      />
      <button type="submit" class="checklist-add" :aria-label="t('checklist.addItem')" :aria-disabled="unavailable">+</button>
    </form>
    <p v-if="error" :id="errorId" class="checklist-error" role="alert">{{ error }}</p>
    <span class="checklist-status" role="status">{{ busy ? t('task.saving') : announcement }}</span>
  </section>
</template>
