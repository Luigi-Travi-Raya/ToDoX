<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Priority } from './api'

const props = withDefaults(
  defineProps<{
    modelValue: Priority
    disabled?: boolean
    compact?: boolean
  }>(),
  {
    disabled: false,
    compact: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: Priority]
}>()

const { t } = useI18n()
const priorities: Priority[] = ['urgent', 'high', 'medium', 'low', 'very_low']
const root = ref<HTMLElement | null>(null)
const open = ref(false)

function toggle() {
  if (!props.disabled) open.value = !open.value
}

function selectPriority(value: Priority) {
  open.value = false
  if (value !== props.modelValue) emit('update:modelValue', value)
}

function closeOnOutsideClick(event: PointerEvent) {
  if (!root.value?.contains(event.target as Node)) open.value = false
}

function handleKeydown(event: KeyboardEvent) {
  if (props.disabled) return
  if (event.key === 'Escape') {
    open.value = false
    return
  }
  if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return

  event.preventDefault()
  const currentIndex = priorities.indexOf(props.modelValue)
  const direction = event.key === 'ArrowDown' ? 1 : -1
  const nextIndex = (currentIndex + direction + priorities.length) % priorities.length
  open.value = true
  emit('update:modelValue', priorities[nextIndex])
}

onMounted(() => document.addEventListener('pointerdown', closeOnOutsideClick))
onBeforeUnmount(() => document.removeEventListener('pointerdown', closeOnOutsideClick))
</script>

<template>
  <div
    ref="root"
    class="priority-select"
    :class="{ compact, open }"
    :data-priority="modelValue"
    @keydown="handleKeydown"
  >
    <button
      class="priority-trigger"
      type="button"
      :disabled="disabled"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="toggle"
    >
      <span class="priority-value">
        <span v-if="!compact" class="priority-dot" aria-hidden="true"></span>
        <span>{{ t(`priority.${modelValue}`) }}</span>
      </span>
      <span class="priority-chevron" aria-hidden="true"></span>
    </button>

    <div v-if="open" class="priority-menu" role="listbox" :aria-label="t('priority.label')">
      <button
        v-for="item in priorities"
        :key="item"
        class="priority-option"
        type="button"
        role="option"
        :data-priority="item"
        :aria-selected="item === modelValue"
        @click="selectPriority(item)"
      >
        <span class="priority-option-label">
          <span v-if="!compact" class="priority-dot" aria-hidden="true"></span>
          <span>{{ t(`priority.${item}`) }}</span>
        </span>
        <span v-if="item === modelValue" aria-hidden="true">✓</span>
      </button>
    </div>
  </div>
</template>
