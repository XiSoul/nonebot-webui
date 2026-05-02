<script setup lang="ts">
import { ensureMonacoWorker } from '@/client/useMonacoWorker'
import { onMounted, ref, watch } from 'vue'
import type { editor as MonacoEditorNamespace } from 'monaco-editor/esm/vs/editor/editor.api.js'

const props = defineProps<{
  modelValue: string
  editorOptional: Partial<MonacoEditorNamespace.IStandaloneEditorConstructionOptions>
}>()

const emit = defineEmits<{
  editor: [value: MonacoEditorNamespace.IStandaloneCodeEditor]
  updateValue: [value: string]
}>()

const editorContainer = ref<HTMLDivElement>()
let editor: MonacoEditorNamespace.IStandaloneCodeEditor

onMounted(async () => {
  await ensureMonacoWorker()
  const { editor: monacoEditor } = await import('monaco-editor/esm/vs/editor/editor.api.js')

  editor = monacoEditor.create(editorContainer.value!, {
    value: props.modelValue,
    ...props.editorOptional
  })
  emit('editor', editor)
  editor.onDidChangeModelContent(() => {
    emit('updateValue', editor.getValue())
  })
})

watch(
  () => props.modelValue,
  (value) => {
    if (!editor) return
    if (value === editor.getValue()) return
    editor.setValue(value)
  }
)
</script>

<template>
  <div ref="editorContainer"></div>
</template>
