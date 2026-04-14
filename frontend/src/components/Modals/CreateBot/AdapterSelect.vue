<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { StoreService, type Adapter } from '@/client/api'
import { useToastStore } from '@/stores'
import ItemSelect from './ItemSelect.vue'
import { useCreateBotStore } from '.'

const store = useCreateBotStore()
const toast = useToastStore()

const adapterList = ref<Adapter[]>([])
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

const requestAdapterList = async (showAll: boolean, page: number) => {
  const { data, error } = await StoreService.getNonebotStoreItemsV1StoreNonebotListGet({
    query: {
      module_type: 'adapter',
      page,
      is_search: false,
      show_all: showAll
    }
  })
  return { data, error }
}

const loadAdapterList = async () => {
  loading.value = true
  loadError.value = ''

  const primary = await requestAdapterList(true, 0)
  if (primary.error) {
    loadError.value = `适配器列表加载失败：${getErrorMessage(primary.error)}`
    toast.add('error', loadError.value, '', 5000)
    loading.value = false
    return
  }

  let detail = primary.data?.detail ?? []
  if (!detail.length) {
    const fallback = await requestAdapterList(false, 0)
    if (fallback.error) {
      loadError.value = `适配器列表加载失败：${getErrorMessage(fallback.error)}`
      toast.add('error', loadError.value, '', 5000)
      loading.value = false
      return
    }
    detail = fallback.data?.detail ?? []
  }

  adapterList.value = detail
  if (!adapterList.value.length) {
    toast.add('warning', '未获取到适配器数据，请稍后重试', '', 4000)
  }
  loading.value = false
}

onMounted(() => {
  loadAdapterList()
})
</script>

<template>
  <div class="flex flex-col gap-4 md:gap-8">
    <div v-if="loading" class="w-full p-6 bg-base-200 rounded-lg text-center opacity-70">
      正在加载适配器列表...
    </div>
    <div v-else-if="loadError" class="w-full p-6 bg-base-200 rounded-lg flex items-center justify-between">
      <span>{{ loadError }}</span>
      <button class="btn btn-sm" @click="loadAdapterList">重试</button>
    </div>
    <ItemSelect v-else :data="adapterList" :data-type="'adapter'" />

    <div class="flex justify-between items-center">
      <button class="btn btn-sm btn-primary text-base-100" @click="store.step--">上一步</button>

      <button
        :class="{
          'btn btn-sm btn-primary text-base-100': true,
          'btn-disabled': !store.adapters.length || loading
        }"
        @click="store.step++"
      >
        下一步
      </button>
    </div>
  </div>
</template>
