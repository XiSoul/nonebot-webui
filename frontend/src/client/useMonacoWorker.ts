let monacoReady: Promise<void> | null = null

export const ensureMonacoWorker = async () => {
  if (!monacoReady) {
    monacoReady = (async () => {
      const monaco = await import('monaco-editor/esm/vs/editor/editor.api.js')
      const target = globalThis as typeof globalThis & {
        MonacoEnvironment?: {
          getWorkerUrl: () => string
        }
      }

      if (!target.MonacoEnvironment) {
        target.MonacoEnvironment = {
          getWorkerUrl: () => './editor.worker.bundle.js'
        }
      }

      void monaco
    })()
  }

  return monacoReady
}
