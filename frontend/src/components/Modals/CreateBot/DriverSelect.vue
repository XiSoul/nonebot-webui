<script setup lang="ts">
import { StoreService, type Driver } from '@/client/api'
import { onMounted, ref } from 'vue'
import { useToastStore } from '@/stores'
import ItemSelect from './ItemSelect.vue'
import { useCreateBotStore } from '.'

const store = useCreateBotStore()
const toast = useToastStore()

const driverList = ref<Driver[]>([])
const loading = ref(true)
const loadError = ref('')

const getErrorMessage = (error: any) => {
  if (!error) return '未知错误'
  const detail = error.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item?.msg || JSON.stringify(item)).join('; ')
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return String(error)
}

const requestDriverList = async (showAll: boolean, page: number) => {
  const { data, error } = await StoreService.getNonebotStoreItemsV1StoreNonebotListGet({
    query: {
      module_type: 'driver',
      page,
      is_search: false,
      show_all: showAll
    }
  })
  return { data, error }
}

const loadDriverList = async () => {
  loading.value = true
  loadError.value = ''

  const primary = await requestDriverList(true, 0)
  if (primary.error) {
    loadError.value = `驱动器列表加载失败：${getErrorMessage(primary.error)}`
    toast.add('error', loadError.value, '', 5000)
    loading.value = false
    return
  }

  let detail = primary.data?.detail ?? []
  if (!detail.length) {
    const fallback = await requestDriverList(false, 0)
    if (fallback.error) {
      loadError.value = `驱动器列表加载失败：${getErrorMessage(fallback.error)}`
      toast.add('error', loadError.value, '', 5000)
      loading.value = false
      return
    }
    detail = fallback.data?.detail ?? []
  }

  driverList.value = detail
  if (!driverList.value.length) {
    toast.add('warning', '未获取到驱动器数据，请稍后重试', '', 4000)
  }
  loading.value = false
}

onMounted(() => {
  loadDriverList()
})
</script>

<template>
  <div class="flex flex-col gap-4 md:gap-8">
    <div v-if="loading" class="w-full p-6 bg-base-200 rounded-lg text-center opacity-70">
      正在加载驱动器列表...
    </div>
    <div v-else-if="loadError" class="w-full p-6 bg-base-200 rounded-lg flex items-center justify-between">
      <span>{{ loadError }}</span>
      <button class="btn btn-sm" @click="loadDriverList">重试</button>
    </div>
    <ItemSelect v-else :data="driverList" :data-type="'driver'" />

    <div class="flex justify-between items-center">
      <button class="btn btn-sm btn-primary text-base-100" @click="store.step--">上一步</button>

      <button
        :class="{
          'btn btn-sm btn-primary text-base-100': true,
          'btn-disabled': !store.drivers.length || loading
        }"
        @click="store.step++"
      >
        下一步
      </button>
    </div>
  </div>
</template>
