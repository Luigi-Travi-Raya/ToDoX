<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { closeQuickWindow, createTask, getSettings, listTasks, showMainWindow, type Priority } from './api'
import PrioritySelect from './PrioritySelect.vue'
import { applyTheme } from './theme'
import { setAppLocale } from './i18n'
import { translatedError } from './i18n/errors'

const { t } = useI18n()
const name = ref('')
const priority = ref<Priority>('medium')
const saving = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    const settings = await getSettings()
    applyTheme(settings.tema)
    setAppLocale(settings.locale)
  } catch {
    applyTheme('dark')
    setAppLocale('en')
  }

  try {
    await listTasks()
  } catch {
    await showMainWindow()
    await closeQuickWindow()
  }
})

async function submit() {
  saving.value = true
  error.value = ''
  try {
    await createTask(name.value, priority.value)
    await closeQuickWindow()
  } catch (cause) {
    error.value = translatedError(t, cause, 'errors.addTask')
    saving.value = false
  }
}
</script>

<template>
  <main class="quick-page" @keydown.esc="closeQuickWindow">
    <p class="eyebrow">{{ t('task.new') }}</p>
    <h1>{{ t('task.addTask') }}</h1>
    <form class="quick-form" @submit.prevent="submit">
      <input
        v-model="name"
        maxlength="180"
        autofocus
        :placeholder="t('task.quickPlaceholder')"
        :aria-label="t('task.name')"
      />
      <div class="quick-actions">
        <PrioritySelect v-model="priority" />
        <button type="submit" :disabled="saving">
          {{ saving ? t('task.saving') : t('task.addTask') }}
        </button>
      </div>
      <p v-if="error" class="editor-error">{{ error }}</p>
    </form>
  </main>
</template>
