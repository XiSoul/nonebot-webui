<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useToastStore } from '@/stores'
import {
  applyContainerRuntimeProfile,
  benchmarkContainerRuntimePresets,
  deleteContainerRuntimeProfile,
  getContainerRuntimeSettings,
  getContainerRuntimeProfiles,
  saveContainerRuntimeProfile,
  testContainerRuntimeSettings,
  updateContainerRuntimeSettings,
  type ContainerRuntimeConnectivityItem,
  type ContainerRuntimeProfile,
  type ContainerRuntimePresetBenchmarkItem,
  type ContainerRuntimeTestMode,
  type ContainerRuntimeSettings
} from './container-client'

const toast = useToastStore()

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const benchmarking = ref(false)
const prechecking = ref(false)
const profileSaving = ref(false)
const profileApplying = ref(false)
const profileDeleting = ref(false)
const isDocker = ref(false)
const currentPreset = ref('custom')
const testMode = ref<ContainerRuntimeTestMode>('quick')
const newProfileName = ref('')
const selectedProfileName = ref('')

const testResults = ref<ContainerRuntimeConnectivityItem[]>([])
const testAllPassed = ref<boolean | null>(null)
const benchmarkResults = ref<ContainerRuntimePresetBenchmarkItem[]>([])
const profiles = ref<ContainerRuntimeProfile[]>([])

const form = ref<Omit<ContainerRuntimeSettings, 'is_docker'>>({
  http_proxy: '',
  https_proxy: '',
  all_proxy: '',
  no_proxy: '',
  debian_mirror: '',
  pip_index_url: '',
  pip_extra_index_url: '',
  pip_trusted_host: ''
})

type SourcePreset = {
  id: string
  name: string
  debian_mirror: string
  pip_index_url: string
  pip_trusted_host: string
}

const presets: SourcePreset[] = [
  {
    id: 'official',
    name: 'Official',
    debian_mirror: '',
    pip_index_url: 'https://pypi.org/simple',
    pip_trusted_host: 'pypi.org files.pythonhosted.org'
  },
  {
    id: 'tuna',
    name: 'Tsinghua TUNA',
    debian_mirror: 'https://mirrors.tuna.tsinghua.edu.cn',
    pip_index_url: 'https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple',
    pip_trusted_host: 'mirrors.tuna.tsinghua.edu.cn'
  },
  {
    id: 'ustc',
    name: 'USTC',
    debian_mirror: 'https://mirrors.ustc.edu.cn',
    pip_index_url: 'https://mirrors.ustc.edu.cn/pypi/web/simple',
    pip_trusted_host: 'mirrors.ustc.edu.cn'
  },
  {
    id: 'aliyun',
    name: 'Aliyun',
    debian_mirror: 'https://mirrors.aliyun.com',
    pip_index_url: 'https://mirrors.aliyun.com/pypi/simple',
    pip_trusted_host: 'mirrors.aliyun.com'
  },
  {
    id: 'huawei',
    name: 'Huawei',
    debian_mirror: 'https://repo.huaweicloud.com',
    pip_index_url: 'https://repo.huaweicloud.com/repository/pypi/simple',
    pip_trusted_host: 'repo.huaweicloud.com'
  }
]

const resetTestResult = () => {
  testResults.value = []
  testAllPassed.value = null
}

const resetBenchmarkResult = () => {
  benchmarkResults.value = []
}

const applyPresetById = (presetId: string) => {
  const preset = presets.find((item) => item.id === presetId)
  if (!preset) return

  form.value.debian_mirror = preset.debian_mirror
  form.value.pip_index_url = preset.pip_index_url
  form.value.pip_extra_index_url = ''
  form.value.pip_trusted_host = preset.pip_trusted_host
  currentPreset.value = presetId
  resetTestResult()
  resetBenchmarkResult()
}

const applyPreset = () => {
  if (currentPreset.value === 'custom') return
  applyPresetById(currentPreset.value)
  const preset = presets.find((item) => item.id === currentPreset.value)
  toast.add('success', `Preset applied: ${preset?.name ?? currentPreset.value}`, '', 3000)
}

const clearAll = () => {
  form.value = {
    http_proxy: '',
    https_proxy: '',
    all_proxy: '',
    no_proxy: '',
    debian_mirror: '',
    pip_index_url: '',
    pip_extra_index_url: '',
    pip_trusted_host: ''
  }
  currentPreset.value = 'custom'
  resetTestResult()
  resetBenchmarkResult()
}

const normalizeProfileName = (name: string) => name.trim()

const loadProfiles = async () => {
  const { data, error } = await getContainerRuntimeProfiles()
  if (error) {
    toast.add('error', `Failed to load profiles: ${error}`, '', 5000)
    return
  }

  const nextProfiles = data ?? []
  profiles.value = nextProfiles

  if (!nextProfiles.find((item) => item.name === selectedProfileName.value)) {
    selectedProfileName.value = ''
  }
}

const applyProfileToForm = (profile: ContainerRuntimeProfile) => {
  form.value = {
    http_proxy: profile.http_proxy,
    https_proxy: profile.https_proxy,
    all_proxy: profile.all_proxy,
    no_proxy: profile.no_proxy,
    debian_mirror: profile.debian_mirror,
    pip_index_url: profile.pip_index_url,
    pip_extra_index_url: profile.pip_extra_index_url,
    pip_trusted_host: profile.pip_trusted_host
  }
  currentPreset.value = 'custom'
  resetTestResult()
  resetBenchmarkResult()
}

const loadSelectedProfileToForm = () => {
  const profile = profiles.value.find((item) => item.name === selectedProfileName.value)
  if (!profile) {
    toast.add('warning', 'Please select a profile first.', '', 3000)
    return
  }
  applyProfileToForm(profile)
  toast.add('success', `Profile loaded: ${profile.name}`, '', 3000)
}

const saveCurrentAsProfile = async () => {
  const name = normalizeProfileName(newProfileName.value)
  if (!name) {
    toast.add('warning', 'Please enter a profile name.', '', 3000)
    return
  }

  profileSaving.value = true
  const { error } = await saveContainerRuntimeProfile(name, form.value)
  profileSaving.value = false

  if (error) {
    toast.add('error', `Save profile failed: ${error}`, '', 5000)
    return
  }

  newProfileName.value = ''
  selectedProfileName.value = name
  await loadProfiles()
  toast.add('success', `Profile saved: ${name}`, '', 3000)
}

const applySelectedProfile = async () => {
  const name = normalizeProfileName(selectedProfileName.value)
  if (!name) {
    toast.add('warning', 'Please select a profile first.', '', 3000)
    return
  }

  profileApplying.value = true
  const { error } = await applyContainerRuntimeProfile(name)
  profileApplying.value = false

  if (error) {
    toast.add('error', `Apply profile failed: ${error}`, '', 5000)
    return
  }

  await loadSettings()
  await loadProfiles()
  toast.add('success', `Profile applied: ${name}`, '', 4000)
}

const deleteSelectedProfile = async () => {
  const name = normalizeProfileName(selectedProfileName.value)
  if (!name) {
    toast.add('warning', 'Please select a profile first.', '', 3000)
    return
  }

  const confirmed = window.confirm(`Delete profile "${name}"?`)
  if (!confirmed) return

  profileDeleting.value = true
  const { error } = await deleteContainerRuntimeProfile(name)
  profileDeleting.value = false

  if (error) {
    toast.add('error', `Delete profile failed: ${error}`, '', 5000)
    return
  }

  selectedProfileName.value = ''
  await loadProfiles()
  toast.add('success', `Profile deleted: ${name}`, '', 3000)
}

const loadSettings = async () => {
  loading.value = true
  const { data, error } = await getContainerRuntimeSettings()
  loading.value = false

  if (error) {
    toast.add('error', `Failed to load container settings: ${error}`, '', 5000)
    return
  }

  if (!data) return
  isDocker.value = data.is_docker
  form.value = {
    http_proxy: data.http_proxy,
    https_proxy: data.https_proxy,
    all_proxy: data.all_proxy,
    no_proxy: data.no_proxy,
    debian_mirror: data.debian_mirror,
    pip_index_url: data.pip_index_url,
    pip_extra_index_url: data.pip_extra_index_url,
    pip_trusted_host: data.pip_trusted_host
  }
  resetTestResult()
  resetBenchmarkResult()
}

const saveSettings = async () => {
  prechecking.value = true
  const check = await testContainerRuntimeSettings(form.value, 'quick')
  prechecking.value = false
  if (check.error) {
    toast.add('error', `Pre-check failed: ${check.error}`, '', 5000)
    return false
  }

  if (check.data) {
    testResults.value = check.data.results
    testAllPassed.value = check.data.ok

    const failedItems = check.data.results.filter((item) => !item.ok && !item.skipped)
    if (failedItems.length > 0) {
      const failedNames = failedItems.map((item) => item.name).join(', ')
      const confirmed = window.confirm(
        `Quick connectivity check failed (${failedNames}). Save and apply anyway?`
      )
      if (!confirmed) {
        toast.add('warning', 'Save cancelled by user.', '', 3000)
        return false
      }
    }
  }

  saving.value = true
  const { error } = await updateContainerRuntimeSettings(form.value)
  saving.value = false

  if (error) {
    toast.add('error', `Save failed: ${error}`, '', 5000)
    return false
  }

  toast.add('success', 'Saved and applied.', '', 5000)
  return true
}

const rollbackOfficial = async () => {
  applyPresetById('official')
  const ok = await saveSettings()
  if (ok) toast.add('success', 'Rolled back to official source.', '', 4000)
}

const runConnectivityTest = async () => {
  testing.value = true
  const { data, error } = await testContainerRuntimeSettings(form.value, testMode.value)
  testing.value = false

  if (error) {
    toast.add('error', `Connectivity test failed: ${error}`, '', 5000)
    return
  }

  if (!data) return
  testResults.value = data.results
  testAllPassed.value = data.ok

  if (data.results.length === 0) {
    toast.add('warning', 'No mirror targets to test.', '', 3000)
  } else if (data.ok) {
    toast.add('success', 'All connectivity checks passed.', '', 3000)
  } else {
    toast.add('warning', 'Some connectivity checks failed.', '', 5000)
  }
}

const runPresetBenchmark = async () => {
  benchmarking.value = true
  const { data, error } = await benchmarkContainerRuntimePresets({
    http_proxy: form.value.http_proxy,
    https_proxy: form.value.https_proxy,
    all_proxy: form.value.all_proxy,
    no_proxy: form.value.no_proxy
  })
  benchmarking.value = false

  if (error) {
    toast.add('error', `Preset benchmark failed: ${error}`, '', 5000)
    return
  }

  if (!data) return
  benchmarkResults.value = data.results

  const best = data.results.find((item) => item.ok)
  if (best) {
    toast.add('success', `Best preset: ${best.preset_name}`, '', 3000)
  } else {
    toast.add('warning', 'No available preset passed benchmark.', '', 4000)
  }
}

const applyBenchmarkPreset = (presetId: string) => {
  applyPresetById(presetId)
  const preset = presets.find((item) => item.id === presetId)
  toast.add('success', `Preset selected from benchmark: ${preset?.name ?? presetId}`, '', 3000)
}

const bestBenchmarkPreset = computed(() => {
  return benchmarkResults.value.find((item) => item.ok)
})

const applyBestBenchmarkPresetAndSave = async () => {
  const best = bestBenchmarkPreset.value
  if (!best) {
    toast.add('warning', 'No available benchmark result to apply.', '', 3000)
    return
  }
  applyPresetById(best.preset_id)
  const ok = await saveSettings()
  if (ok) {
    toast.add('success', `Best preset applied: ${best.preset_name}`, '', 4000)
  }
}

const testSummaryClass = computed(() => {
  if (testAllPassed.value === null) return 'badge-ghost'
  return testAllPassed.value ? 'badge-success' : 'badge-warning'
})

const hasProfileSelection = computed(() => {
  return normalizeProfileName(selectedProfileName.value).length > 0
})

const loadAllData = async () => {
  await Promise.all([loadSettings(), loadProfiles()])
}

onMounted(loadAllData)
</script>

<template>
  <div class="w-full p-6 bg-base-200 rounded-box flex flex-col gap-4">
    <div class="flex flex-col gap-2">
      <h2 class="text-xl font-semibold">Container Proxy And Mirrors</h2>
      <div class="text-sm opacity-70">
        Configure proxy, Debian/APT mirror and pip source for Docker runtime.
      </div>
      <div class="text-xs opacity-60">Runtime: {{ isDocker ? 'Docker' : 'Non-Docker' }}</div>
      <div class="bg-base-content/10 h-[1px]"></div>
    </div>

    <div v-if="loading" class="text-sm opacity-70">Loading...</div>

    <div v-else class="flex flex-col gap-4">
      <div class="p-3 rounded-lg bg-base-100 flex flex-col md:flex-row gap-2 md:items-center">
        <span class="text-sm opacity-70 min-w-fit">One Click Preset</span>
        <select v-model="currentPreset" class="select select-sm select-bordered flex-1">
          <option value="custom">Custom</option>
          <option v-for="preset in presets" :key="preset.id" :value="preset.id">
            {{ preset.name }}
          </option>
        </select>
        <button class="btn btn-sm" :disabled="currentPreset === 'custom'" @click="applyPreset">
          Apply Preset
        </button>
        <button class="btn btn-sm btn-ghost" @click="clearAll">Clear</button>
        <button class="btn btn-sm btn-outline btn-warning" :disabled="saving" @click="rollbackOfficial">
          Rollback Official
        </button>
      </div>

      <div class="p-3 rounded-lg bg-base-100 flex flex-col gap-2">
        <div class="flex flex-col md:flex-row gap-2 md:items-center">
          <span class="text-sm opacity-70 min-w-fit">Runtime Profile</span>
          <input
            v-model="newProfileName"
            class="input input-sm input-bordered md:w-64"
            placeholder="e.g. home-proxy"
          />
          <button
            class="btn btn-sm"
            :disabled="profileSaving || profileApplying || profileDeleting"
            @click="saveCurrentAsProfile"
          >
            {{ profileSaving ? 'Saving...' : 'Save Current As Profile' }}
          </button>
        </div>

        <div class="flex flex-col md:flex-row gap-2 md:items-center">
          <select v-model="selectedProfileName" class="select select-sm select-bordered flex-1">
            <option value="">Select Profile</option>
            <option v-for="profile in profiles" :key="profile.name" :value="profile.name">
              {{ profile.name }}
            </option>
          </select>
          <button
            class="btn btn-sm btn-ghost"
            :disabled="!hasProfileSelection"
            @click="loadSelectedProfileToForm"
          >
            Load To Form
          </button>
          <button
            class="btn btn-sm"
            :disabled="!hasProfileSelection || profileSaving || profileApplying || profileDeleting"
            @click="applySelectedProfile"
          >
            {{ profileApplying ? 'Applying...' : 'Apply Profile' }}
          </button>
          <button
            class="btn btn-sm btn-outline btn-error"
            :disabled="!hasProfileSelection || profileSaving || profileApplying || profileDeleting"
            @click="deleteSelectedProfile"
          >
            {{ profileDeleting ? 'Deleting...' : 'Delete Profile' }}
          </button>
        </div>
      </div>

      <div class="text-xs opacity-70">
        For Linux hosts using host proxy, add
        <code>--add-host host.docker.internal:host-gateway</code> in docker run.
      </div>

      <div class="p-3 rounded-lg bg-base-100 flex flex-col md:flex-row gap-2 md:items-center">
        <span class="text-sm opacity-70 min-w-fit">Test Mode</span>
        <select v-model="testMode" class="select select-sm select-bordered md:w-60">
          <option value="quick">Quick (HTTP)</option>
          <option value="deep">Deep (HTTP + apt/pip)</option>
        </select>
        <span class="text-xs opacity-70">
          Deep mode runs apt and pip command checks in container.
        </span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="form-control w-full">
          <div class="label py-1"><span class="label-text">HTTP_PROXY</span></div>
          <input v-model="form.http_proxy" class="input input-sm input-bordered font-mono" />
        </label>
        <label class="form-control w-full">
          <div class="label py-1"><span class="label-text">HTTPS_PROXY</span></div>
          <input v-model="form.https_proxy" class="input input-sm input-bordered font-mono" />
        </label>
        <label class="form-control w-full">
          <div class="label py-1"><span class="label-text">ALL_PROXY</span></div>
          <input v-model="form.all_proxy" class="input input-sm input-bordered font-mono" />
        </label>
        <label class="form-control w-full">
          <div class="label py-1"><span class="label-text">NO_PROXY</span></div>
          <input v-model="form.no_proxy" class="input input-sm input-bordered font-mono" />
        </label>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="form-control w-full md:col-span-2">
          <div class="label py-1"><span class="label-text">Debian/APT Mirror</span></div>
          <input v-model="form.debian_mirror" class="input input-sm input-bordered font-mono" />
        </label>
        <label class="form-control w-full md:col-span-2">
          <div class="label py-1"><span class="label-text">PIP_INDEX_URL</span></div>
          <input v-model="form.pip_index_url" class="input input-sm input-bordered font-mono" />
        </label>
        <label class="form-control w-full md:col-span-2">
          <div class="label py-1"><span class="label-text">PIP_EXTRA_INDEX_URL</span></div>
          <input
            v-model="form.pip_extra_index_url"
            class="input input-sm input-bordered font-mono"
          />
        </label>
        <label class="form-control w-full md:col-span-2">
          <div class="label py-1"><span class="label-text">PIP_TRUSTED_HOST</span></div>
          <input
            v-model="form.pip_trusted_host"
            class="input input-sm input-bordered font-mono"
          />
        </label>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2">
        <button class="btn btn-sm" :disabled="benchmarking || prechecking || saving" @click="runPresetBenchmark">
          {{ benchmarking ? 'Benchmarking...' : 'Benchmark Presets' }}
        </button>
        <button
          class="btn btn-sm btn-outline"
          :disabled="!bestBenchmarkPreset || saving || prechecking"
          @click="applyBestBenchmarkPresetAndSave"
        >
          Apply Best And Save
        </button>
        <button class="btn btn-sm" :disabled="testing || prechecking || saving" @click="runConnectivityTest">
          {{ testing ? 'Testing...' : 'Connectivity Test' }}
        </button>
        <button class="btn btn-sm btn-primary text-base-100" :disabled="saving || prechecking" @click="saveSettings">
          {{ prechecking ? 'Pre-checking...' : saving ? 'Saving...' : 'Save And Apply' }}
        </button>
      </div>

      <div v-if="testAllPassed !== null" class="flex items-center gap-2">
        <span class="badge" :class="testSummaryClass">
          {{ testAllPassed ? 'PASS' : 'PARTIAL FAIL' }}
        </span>
        <span class="text-xs opacity-70">{{ testResults.length }} checks</span>
      </div>

      <div v-if="testResults.length" class="overflow-x-auto rounded-box border border-base-content/10">
        <table class="table table-xs">
          <thead>
            <tr>
              <th>Item</th>
              <th>Status</th>
              <th>HTTP</th>
              <th>Latency</th>
              <th>Target</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in testResults" :key="`${item.name}-${item.target}`">
              <td class="font-mono">{{ item.name }}</td>
              <td>
                <span
                  class="badge badge-xs"
                  :class="item.skipped ? 'badge-ghost' : item.ok ? 'badge-success' : 'badge-warning'"
                >
                  {{ item.skipped ? 'SKIP' : item.ok ? 'OK' : 'FAIL' }}
                </span>
              </td>
              <td>{{ item.status_code || '-' }}</td>
              <td>{{ item.elapsed_ms }}ms</td>
              <td class="font-mono break-all">{{ item.target }}</td>
              <td class="font-mono break-all text-xs">{{ item.error || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div
        v-if="benchmarkResults.length"
        class="overflow-x-auto rounded-box border border-base-content/10"
      >
        <table class="table table-xs">
          <thead>
            <tr>
              <th>Preset</th>
              <th>Status</th>
              <th>Score</th>
              <th>Debian</th>
              <th>PIP</th>
              <th>Error</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in benchmarkResults" :key="item.preset_id">
              <td class="font-mono">
                {{ item.preset_name }}
                <span
                  v-if="bestBenchmarkPreset && bestBenchmarkPreset.preset_id === item.preset_id"
                  class="badge badge-xs badge-success ml-1"
                >
                  BEST
                </span>
              </td>
              <td>
                <span class="badge badge-xs" :class="item.ok ? 'badge-success' : 'badge-warning'">
                  {{ item.ok ? 'OK' : 'FAIL' }}
                </span>
              </td>
              <td>{{ item.score_ms }}ms</td>
              <td>{{ item.debian_elapsed_ms }}ms</td>
              <td>{{ item.pip_elapsed_ms }}ms</td>
              <td class="font-mono break-all text-xs">{{ item.error || '-' }}</td>
              <td>
                <button class="btn btn-xs" @click="applyBenchmarkPreset(item.preset_id)">Use</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
