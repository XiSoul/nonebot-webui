export type ThemeMode = 'light' | 'dark'
export type ThemePresetId = 'classic' | 'frost' | 'paper' | 'midnight'
export type ThemeAccentId = 'ember' | 'ocean' | 'emerald' | 'violet' | 'amber'

export const THEME_STORAGE_KEYS = {
  mode: 'theme',
  followSystem: 'isThemeFollowSystem',
  preset: 'themePreset',
  accent: 'themeAccent'
} as const

export const THEME_PRESETS = [
  {
    id: 'classic',
    label: 'Classic',
    description: '清爽中性，适合日常长期使用。',
    preview: ['#f8fafc', '#dbe4f0', '#111827']
  },
  {
    id: 'frost',
    label: 'Frost',
    description: '冷调雾感，界面层次更柔和。',
    preview: ['#eff6ff', '#bfdbfe', '#1d4ed8']
  },
  {
    id: 'paper',
    label: 'Paper',
    description: '暖白纸感，阅读和表单更温和。',
    preview: ['#fff7ed', '#fed7aa', '#9a3412']
  },
  {
    id: 'midnight',
    label: 'Midnight',
    description: '深海蓝调，暗色下更沉浸。',
    preview: ['#dbeafe', '#1d4ed8', '#0f172a']
  }
] as const satisfies readonly {
  id: ThemePresetId
  label: string
  description: string
  preview: readonly [string, string, string]
}[]

export const THEME_ACCENTS = [
  { id: 'ember', label: '赤焰', color: '#EA5353' },
  { id: 'ocean', label: '海蓝', color: '#2F80ED' },
  { id: 'emerald', label: '翠绿', color: '#10B981' },
  { id: 'violet', label: '紫曜', color: '#8B5CF6' },
  { id: 'amber', label: '琥珀', color: '#F59E0B' }
] as const satisfies readonly {
  id: ThemeAccentId
  label: string
  color: string
}[]

export const DEFAULT_THEME_MODE: ThemeMode = 'light'
export const DEFAULT_THEME_PRESET: ThemePresetId = 'classic'
export const DEFAULT_THEME_ACCENT: ThemeAccentId = 'ember'

const THEME_MODE_SET = new Set<ThemeMode>(['light', 'dark'])
const THEME_PRESET_SET = new Set<ThemePresetId>(THEME_PRESETS.map((item) => item.id))
const THEME_ACCENT_SET = new Set<ThemeAccentId>(THEME_ACCENTS.map((item) => item.id))

export interface ThemePreferenceSnapshot {
  followSystem: boolean
  manualMode: ThemeMode
  resolvedMode: ThemeMode
  preset: ThemePresetId
  accent: ThemeAccentId
  resolvedThemeId: string
}

export interface ThemeSurfaceStyle {
  appGradient: string
  appTexture: string
  shellBackground: string
  shellBorder: string
  shellShadow: string
  shellGlow: string
  sidebarBackground: string
  headerBackground: string
  panelBackground: string
  panelMutedBackground: string
}

const safeGetLocalStorageItem = (key: string) => {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

const safeSetLocalStorageItem = (key: string, value: string) => {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Ignore storage failures so the UI can still work in restricted contexts.
  }
}

export const isThemeMode = (value: string | null | undefined): value is ThemeMode =>
  value != null && THEME_MODE_SET.has(value as ThemeMode)

export const isThemePresetId = (value: string | null | undefined): value is ThemePresetId =>
  value != null && THEME_PRESET_SET.has(value as ThemePresetId)

export const isThemeAccentId = (value: string | null | undefined): value is ThemeAccentId =>
  value != null && THEME_ACCENT_SET.has(value as ThemeAccentId)

export const resolveSystemThemeMode = (): ThemeMode =>
  window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'

export const getThemePresetMeta = (presetId: ThemePresetId) =>
  THEME_PRESETS.find((item) => item.id === presetId) ?? THEME_PRESETS[0]

export const getThemeAccentMeta = (accentId: ThemeAccentId) =>
  THEME_ACCENTS.find((item) => item.id === accentId) ?? THEME_ACCENTS[0]

export const getThemeSurfaceStyle = (
  preset: ThemePresetId,
  mode: ThemeMode,
  accent: ThemeAccentId
): ThemeSurfaceStyle => {
  const accentColor = getThemeAccentMeta(accent).color

  if (preset === 'frost') {
    return mode === 'dark'
      ? {
          appGradient:
            'radial-gradient(circle at top left, rgba(96,165,250,0.26), transparent 34%), radial-gradient(circle at top right, rgba(45,212,191,0.18), transparent 28%), linear-gradient(160deg, #07111f 0%, #0f1b2f 48%, #132238 100%)',
          appTexture:
            'linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0))',
          shellBackground: 'rgba(8, 15, 27, 0.58)',
          shellBorder: 'rgba(148, 163, 184, 0.16)',
          shellShadow: '0 30px 80px rgba(2, 6, 23, 0.42)',
          shellGlow: `${accentColor}22`,
          sidebarBackground: 'rgba(9, 17, 31, 0.74)',
          headerBackground: 'rgba(10, 18, 32, 0.66)',
          panelBackground: 'rgba(255, 255, 255, 0.06)',
          panelMutedBackground: 'rgba(255, 255, 255, 0.03)'
        }
      : {
          appGradient:
            'radial-gradient(circle at top left, rgba(96,165,250,0.24), transparent 32%), radial-gradient(circle at top right, rgba(45,212,191,0.16), transparent 28%), linear-gradient(160deg, #f7fbff 0%, #eef6ff 48%, #e6f0ff 100%)',
          appTexture:
            'linear-gradient(135deg, rgba(255,255,255,0.45), rgba(255,255,255,0.05))',
          shellBackground: 'rgba(255, 255, 255, 0.56)',
          shellBorder: 'rgba(148, 163, 184, 0.24)',
          shellShadow: '0 28px 80px rgba(56, 189, 248, 0.16)',
          shellGlow: `${accentColor}22`,
          sidebarBackground: 'rgba(255, 255, 255, 0.64)',
          headerBackground: 'rgba(255, 255, 255, 0.52)',
          panelBackground: 'rgba(255, 255, 255, 0.62)',
          panelMutedBackground: 'rgba(255, 255, 255, 0.36)'
        }
  }

  if (preset === 'paper') {
    return mode === 'dark'
      ? {
          appGradient:
            'radial-gradient(circle at top left, rgba(245,158,11,0.16), transparent 28%), radial-gradient(circle at top right, rgba(234,88,12,0.12), transparent 24%), linear-gradient(180deg, #1a1410 0%, #211813 46%, #281d17 100%)',
          appTexture:
            'repeating-linear-gradient(0deg, rgba(255,255,255,0.018) 0px, rgba(255,255,255,0.018) 1px, transparent 1px, transparent 26px)',
          shellBackground: 'rgba(28, 20, 16, 0.68)',
          shellBorder: 'rgba(180, 132, 84, 0.18)',
          shellShadow: '0 30px 70px rgba(21, 15, 11, 0.45)',
          shellGlow: `${accentColor}1f`,
          sidebarBackground: 'rgba(34, 24, 19, 0.78)',
          headerBackground: 'rgba(38, 27, 20, 0.72)',
          panelBackground: 'rgba(255, 248, 239, 0.05)',
          panelMutedBackground: 'rgba(255, 248, 239, 0.03)'
        }
      : {
          appGradient:
            'radial-gradient(circle at top left, rgba(245,158,11,0.14), transparent 28%), radial-gradient(circle at top right, rgba(251,146,60,0.12), transparent 22%), linear-gradient(180deg, #fffaf2 0%, #f9f1e2 46%, #f4ead8 100%)',
          appTexture:
            'repeating-linear-gradient(0deg, rgba(120, 83, 44, 0.035) 0px, rgba(120, 83, 44, 0.035) 1px, transparent 1px, transparent 26px)',
          shellBackground: 'rgba(255, 252, 246, 0.64)',
          shellBorder: 'rgba(180, 132, 84, 0.22)',
          shellShadow: '0 28px 70px rgba(180, 132, 84, 0.15)',
          shellGlow: `${accentColor}20`,
          sidebarBackground: 'rgba(255, 249, 239, 0.72)',
          headerBackground: 'rgba(255, 252, 246, 0.6)',
          panelBackground: 'rgba(255, 255, 255, 0.52)',
          panelMutedBackground: 'rgba(255, 248, 239, 0.36)'
        }
  }

  if (preset === 'midnight') {
    return mode === 'dark'
      ? {
          appGradient:
            'radial-gradient(circle at top left, rgba(59,130,246,0.22), transparent 34%), radial-gradient(circle at bottom right, rgba(14,165,233,0.16), transparent 26%), linear-gradient(160deg, #050816 0%, #0b1020 46%, #11182d 100%)',
          appTexture:
            'linear-gradient(120deg, rgba(255,255,255,0.05), rgba(255,255,255,0))',
          shellBackground: 'rgba(5, 10, 24, 0.7)',
          shellBorder: 'rgba(96, 165, 250, 0.18)',
          shellShadow: '0 34px 90px rgba(2, 6, 23, 0.5)',
          shellGlow: `${accentColor}24`,
          sidebarBackground: 'rgba(6, 10, 22, 0.82)',
          headerBackground: 'rgba(8, 13, 25, 0.74)',
          panelBackground: 'rgba(255, 255, 255, 0.05)',
          panelMutedBackground: 'rgba(255, 255, 255, 0.025)'
        }
      : {
          appGradient:
            'radial-gradient(circle at top left, rgba(59,130,246,0.18), transparent 30%), radial-gradient(circle at bottom right, rgba(14,165,233,0.14), transparent 24%), linear-gradient(160deg, #edf4ff 0%, #dfeaff 46%, #d3e4ff 100%)',
          appTexture:
            'linear-gradient(120deg, rgba(255,255,255,0.38), rgba(255,255,255,0.05))',
          shellBackground: 'rgba(255, 255, 255, 0.58)',
          shellBorder: 'rgba(96, 165, 250, 0.18)',
          shellShadow: '0 30px 72px rgba(37, 99, 235, 0.16)',
          shellGlow: `${accentColor}20`,
          sidebarBackground: 'rgba(241, 247, 255, 0.72)',
          headerBackground: 'rgba(255, 255, 255, 0.52)',
          panelBackground: 'rgba(255, 255, 255, 0.56)',
          panelMutedBackground: 'rgba(255, 255, 255, 0.36)'
        }
  }

  return mode === 'dark'
    ? {
        appGradient:
          'radial-gradient(circle at top left, rgba(99,102,241,0.16), transparent 28%), radial-gradient(circle at bottom right, rgba(16,185,129,0.12), transparent 24%), linear-gradient(160deg, #0f172a 0%, #162033 48%, #1c2940 100%)',
        appTexture:
          'linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0))',
        shellBackground: 'rgba(15, 23, 42, 0.62)',
        shellBorder: 'rgba(148, 163, 184, 0.16)',
        shellShadow: '0 28px 80px rgba(2, 6, 23, 0.42)',
        shellGlow: `${accentColor}20`,
        sidebarBackground: 'rgba(15, 23, 42, 0.76)',
        headerBackground: 'rgba(15, 23, 42, 0.66)',
        panelBackground: 'rgba(255, 255, 255, 0.05)',
        panelMutedBackground: 'rgba(255, 255, 255, 0.025)'
      }
    : {
        appGradient:
          'radial-gradient(circle at top left, rgba(59,130,246,0.12), transparent 28%), radial-gradient(circle at bottom right, rgba(16,185,129,0.1), transparent 24%), linear-gradient(160deg, #f8fafc 0%, #eef3f9 48%, #e6edf6 100%)',
        appTexture:
          'linear-gradient(135deg, rgba(255,255,255,0.36), rgba(255,255,255,0.06))',
        shellBackground: 'rgba(255, 255, 255, 0.56)',
        shellBorder: 'rgba(148, 163, 184, 0.18)',
        shellShadow: '0 28px 72px rgba(15, 23, 42, 0.12)',
        shellGlow: `${accentColor}18`,
        sidebarBackground: 'rgba(255, 255, 255, 0.64)',
        headerBackground: 'rgba(255, 255, 255, 0.48)',
        panelBackground: 'rgba(255, 255, 255, 0.58)',
        panelMutedBackground: 'rgba(255, 255, 255, 0.34)'
      }
}

export const buildResolvedThemeId = (
  preset: ThemePresetId,
  mode: ThemeMode,
  accent: ThemeAccentId
) => `nb-${preset}-${mode}-${accent}`

export const getStoredThemePreferences = (): ThemePreferenceSnapshot => {
  const followSystem = safeGetLocalStorageItem(THEME_STORAGE_KEYS.followSystem) !== '0'

  const storedMode = safeGetLocalStorageItem(THEME_STORAGE_KEYS.mode)
  const manualMode = isThemeMode(storedMode) ? storedMode : DEFAULT_THEME_MODE

  const storedPreset = safeGetLocalStorageItem(THEME_STORAGE_KEYS.preset)
  const preset = isThemePresetId(storedPreset) ? storedPreset : DEFAULT_THEME_PRESET

  const storedAccent = safeGetLocalStorageItem(THEME_STORAGE_KEYS.accent)
  const accent = isThemeAccentId(storedAccent) ? storedAccent : DEFAULT_THEME_ACCENT

  const resolvedMode = followSystem ? resolveSystemThemeMode() : manualMode

  return {
    followSystem,
    manualMode,
    resolvedMode,
    preset,
    accent,
    resolvedThemeId: buildResolvedThemeId(preset, resolvedMode, accent)
  }
}

export const applyThemeSelection = (selection: {
  mode: ThemeMode
  preset: ThemePresetId
  accent: ThemeAccentId
}) => {
  const resolvedThemeId = buildResolvedThemeId(
    selection.preset,
    selection.mode,
    selection.accent
  )
  const accent = getThemeAccentMeta(selection.accent)
  const surface = getThemeSurfaceStyle(selection.preset, selection.mode, selection.accent)
  const root = document.documentElement

  root.setAttribute('data-theme', resolvedThemeId)
  root.dataset.themeMode = selection.mode
  root.dataset.themePreset = selection.preset
  root.dataset.themeAccent = selection.accent
  root.style.colorScheme = selection.mode
  root.style.setProperty('--nb-accent-color', accent.color)
  root.style.setProperty('--nb-app-gradient', surface.appGradient)
  root.style.setProperty('--nb-app-texture', surface.appTexture)
  root.style.setProperty('--nb-shell-bg', surface.shellBackground)
  root.style.setProperty('--nb-shell-border', surface.shellBorder)
  root.style.setProperty('--nb-shell-shadow', surface.shellShadow)
  root.style.setProperty('--nb-shell-glow', surface.shellGlow)
  root.style.setProperty('--nb-sidebar-bg', surface.sidebarBackground)
  root.style.setProperty('--nb-header-bg', surface.headerBackground)
  root.style.setProperty('--nb-panel-bg', surface.panelBackground)
  root.style.setProperty('--nb-panel-muted-bg', surface.panelMutedBackground)

  return resolvedThemeId
}

export const applyStoredThemeSelection = () => {
  const snapshot = getStoredThemePreferences()
  applyThemeSelection({
    mode: snapshot.resolvedMode,
    preset: snapshot.preset,
    accent: snapshot.accent
  })
  return snapshot
}

export const persistThemeMode = (mode: ThemeMode) =>
  safeSetLocalStorageItem(THEME_STORAGE_KEYS.mode, mode)

export const persistThemeFollowSystem = (followSystem: boolean) =>
  safeSetLocalStorageItem(THEME_STORAGE_KEYS.followSystem, followSystem ? '1' : '0')

export const persistThemePreset = (preset: ThemePresetId) =>
  safeSetLocalStorageItem(THEME_STORAGE_KEYS.preset, preset)

export const persistThemeAccent = (accent: ThemeAccentId) =>
  safeSetLocalStorageItem(THEME_STORAGE_KEYS.accent, accent)
