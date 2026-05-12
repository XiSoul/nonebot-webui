const baseThemes = require('daisyui/src/theming/themes')

const themePresets = {
  classic: {
    light: {
      name: 'corporate',
      overrides: {
        'base-100': '#f8fafc',
        'base-200': '#eef2f7',
        'base-300': '#dce3ed',
        'base-content': '#111827',
        neutral: '#1f2937',
        'neutral-content': '#f9fafb',
        info: '#2563eb',
        success: '#16a34a',
        warning: '#d97706',
        error: '#dc2626'
      }
    },
    dark: {
      name: 'business',
      overrides: {
        'base-100': '#111827',
        'base-200': '#182235',
        'base-300': '#243044',
        'base-content': '#e5eefc',
        neutral: '#0b1220',
        'neutral-content': '#eff6ff',
        info: '#60a5fa',
        success: '#34d399',
        warning: '#fbbf24',
        error: '#f87171'
      }
    }
  },
  frost: {
    light: {
      name: 'winter',
      overrides: {
        'base-100': '#f4f8ff',
        'base-200': '#e8f0ff',
        'base-300': '#cfddf7',
        'base-content': '#1e293b',
        neutral: '#274c77',
        'neutral-content': '#eff6ff',
        info: '#2563eb',
        success: '#0f766e',
        warning: '#d97706',
        error: '#dc2626'
      }
    },
    dark: {
      name: 'night',
      overrides: {
        'base-100': '#0b1220',
        'base-200': '#111b2e',
        'base-300': '#17243a',
        'base-content': '#d7e3f7',
        neutral: '#030712',
        'neutral-content': '#e5eefc',
        info: '#60a5fa',
        success: '#2dd4bf',
        warning: '#fbbf24',
        error: '#fb7185'
      }
    }
  },
  paper: {
    light: {
      name: 'lofi',
      overrides: {
        'base-100': '#fffaf2',
        'base-200': '#f8eedf',
        'base-300': '#ecd8bf',
        'base-content': '#3f3a34',
        neutral: '#6b4f3a',
        'neutral-content': '#fffaf2',
        info: '#3b82f6',
        success: '#65a30d',
        warning: '#d97706',
        error: '#dc2626'
      }
    },
    dark: {
      name: 'coffee',
      overrides: {
        'base-100': '#211d1a',
        'base-200': '#2d2622',
        'base-300': '#3a302a',
        'base-content': '#f5eadf',
        neutral: '#171311',
        'neutral-content': '#fff7ed',
        info: '#60a5fa',
        success: '#84cc16',
        warning: '#f59e0b',
        error: '#fb7185'
      }
    }
  },
  midnight: {
    light: {
      name: 'cupcake',
      overrides: {
        'base-100': '#eef4ff',
        'base-200': '#dce8ff',
        'base-300': '#bfd4ff',
        'base-content': '#1f2a44',
        neutral: '#283a63',
        'neutral-content': '#eef4ff',
        info: '#2563eb',
        success: '#059669',
        warning: '#d97706',
        error: '#dc2626'
      }
    },
    dark: {
      name: 'dim',
      overrides: {
        'base-100': '#0f172a',
        'base-200': '#172033',
        'base-300': '#243047',
        'base-content': '#e2e8f0',
        neutral: '#020617',
        'neutral-content': '#dbeafe',
        info: '#60a5fa',
        success: '#34d399',
        warning: '#fbbf24',
        error: '#f87171'
      }
    }
  }
}

const themeAccents = {
  ember: '#EA5353',
  ocean: '#2F80ED',
  emerald: '#10B981',
  violet: '#8B5CF6',
  amber: '#F59E0B'
}

const createThemeVariant = ({ presetId, mode, accentId, accentColor }) => {
  const preset = themePresets[presetId][mode]
  const baseTheme = baseThemes[preset.name]

  return {
    [`nb-${presetId}-${mode}-${accentId}`]: {
      ...baseTheme,
      ...preset.overrides,
      primary: accentColor,
      secondary: accentColor,
      accent: accentColor
    }
  }
}

const daisyThemes = Object.entries(themePresets).flatMap(([presetId]) =>
  Object.entries(themeAccents).flatMap(([accentId, accentColor]) =>
    ['light', 'dark'].map((mode) =>
      createThemeVariant({
        presetId,
        mode,
        accentId,
        accentColor
      })
    )
  )
)

module.exports = {
  daisyThemes
}
