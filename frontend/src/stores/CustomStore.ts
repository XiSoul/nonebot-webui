import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useStatusStore } from './StatusStore'
import { v4 as uuidv4 } from 'uuid'
import {
  DEFAULT_THEME_ACCENT,
  DEFAULT_THEME_MODE,
  DEFAULT_THEME_PRESET,
  THEME_ACCENTS,
  THEME_PRESETS,
  type ThemeAccentId,
  type ThemeMode,
  type ThemePresetId,
  applyThemeSelection,
  buildResolvedThemeId,
  getStoredThemePreferences,
  persistThemeAccent,
  persistThemeFollowSystem,
  persistThemeMode,
  persistThemePreset,
  resolveSystemThemeMode
} from '@/theme/webuiTheme'

const ID_OF_DEBUG_STATUS = uuidv4()

export const useCustomStore = defineStore('customStore', () => {
  let data: string | null

  const statusStore = useStatusStore()

  const isDebug = ref(false)

  data = localStorage.getItem('isDebug')
  if (data) {
    isDebug.value = data === '1'
    if (isDebug.value) statusStore.update(ID_OF_DEBUG_STATUS, 'badge-warning', '开发模式')
  }

  const toggleDebug = () => {
    isDebug.value = !isDebug.value
    localStorage.setItem('isDebug', isDebug.value ? '1' : '0')

    if (isDebug.value) {
      statusStore.update(ID_OF_DEBUG_STATUS, 'badge-warning', '开发模式')
    } else {
      statusStore.deleteStatus(ID_OF_DEBUG_STATUS)
    }
  }

  const storedTheme = getStoredThemePreferences()

  const isThemeFollowSystem = ref(storedTheme.followSystem)
  const currentTheme = ref<ThemeMode>(storedTheme.resolvedMode)
  const preferredTheme = ref<ThemeMode>(storedTheme.manualMode)
  const currentThemePreset = ref<ThemePresetId>(storedTheme.preset)
  const currentThemeAccent = ref<ThemeAccentId>(storedTheme.accent)

  const themePresetOptions = THEME_PRESETS
  const themeAccentOptions = THEME_ACCENTS

  const resolvedThemeId = computed(() =>
    buildResolvedThemeId(
      currentThemePreset.value,
      currentTheme.value,
      currentThemeAccent.value
    )
  )

  const applyResolvedTheme = (mode: ThemeMode = currentTheme.value) => {
    currentTheme.value = mode
    applyThemeSelection({
      mode,
      preset: currentThemePreset.value,
      accent: currentThemeAccent.value
    })
  }

  const setThemeMode = (theme: ThemeMode) => {
    preferredTheme.value = theme
    persistThemeMode(theme)
    if (!isThemeFollowSystem.value) {
      applyResolvedTheme(theme)
    }
  }

  const toggleTheme = (theme: ThemeMode) => {
    if (isThemeFollowSystem.value) {
      isThemeFollowSystem.value = false
      persistThemeFollowSystem(false)
    }
    setThemeMode(theme)
    applyResolvedTheme(theme)
  }

  const toggleThemeFollowSystem = () => {
    isThemeFollowSystem.value = !isThemeFollowSystem.value
    persistThemeFollowSystem(isThemeFollowSystem.value)
    if (isThemeFollowSystem.value) {
      applyResolvedTheme(resolveSystemThemeMode())
      return
    }
    applyResolvedTheme(preferredTheme.value)
  }

  const syncThemeWithSystem = () => {
    if (!isThemeFollowSystem.value) return
    applyResolvedTheme(resolveSystemThemeMode())
  }

  const setThemePreset = (preset: ThemePresetId) => {
    currentThemePreset.value = preset
    persistThemePreset(preset)
    applyResolvedTheme()
  }

  const setThemeAccent = (accent: ThemeAccentId) => {
    currentThemeAccent.value = accent
    persistThemeAccent(accent)
    applyResolvedTheme()
  }

  applyResolvedTheme(isThemeFollowSystem.value ? resolveSystemThemeMode() : preferredTheme.value)

  const isInstantSearch = ref(false)

  data = localStorage.getItem('instantSearch')
  if (data) {
    isInstantSearch.value = data === '1'
  }

  const toggleInstantSearch = () => {
    isInstantSearch.value = !isInstantSearch.value
    localStorage.setItem('instantSearch', isInstantSearch.value ? '1' : '0')
  }

  const menuMinify = ref(false)

  const toggleMenuMinify = () => {
    menuMinify.value = !menuMinify.value
  }

  const menuShow = ref(false)

  const toggleMenuShow = () => {
    menuShow.value = !menuShow.value
  }

  const resetTheme = () => {
    preferredTheme.value = DEFAULT_THEME_MODE
    currentThemePreset.value = DEFAULT_THEME_PRESET
    currentThemeAccent.value = DEFAULT_THEME_ACCENT
    persistThemeMode(DEFAULT_THEME_MODE)
    persistThemePreset(DEFAULT_THEME_PRESET)
    persistThemeAccent(DEFAULT_THEME_ACCENT)
    applyResolvedTheme(isThemeFollowSystem.value ? resolveSystemThemeMode() : DEFAULT_THEME_MODE)
  }

  return {
    isDebug,
    toggleDebug,
    isThemeFollowSystem,
    toggleThemeFollowSystem,
    currentTheme,
    preferredTheme,
    toggleTheme,
    setThemeMode,
    syncThemeWithSystem,
    currentThemePreset,
    currentThemeAccent,
    themePresetOptions,
    themeAccentOptions,
    setThemePreset,
    setThemeAccent,
    resolvedThemeId,
    resetTheme,
    isInstantSearch,
    toggleInstantSearch,
    menuMinify,
    toggleMenuMinify,
    menuShow,
    toggleMenuShow
  }
})
