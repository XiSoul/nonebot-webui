import {
  type Adapter,
  type Driver,
  type nb_cli_plugin_webui__app__models__store__Plugin,
  StoreService,
  type ModuleType,
  type nb_cli_plugin_webui__app__models__store__SearchTag
} from '@/client/api'
import { useToastStore } from '@/stores'
import { defineStore } from 'pinia'
import { ref } from 'vue'

const toast = useToastStore()

const getErrorMessage = (error: any) => {
  if (!error) return '未知错误'
  const detail = error.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || JSON.stringify(item)).join('; ')
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return String(error)
}

export const useSearchStore = defineStore('storeSearchStore', () => {
  const searchInput = ref('')
  const searchTags = ref<nb_cli_plugin_webui__app__models__store__SearchTag[]>([])
  const storeData = ref<(nb_cli_plugin_webui__app__models__store__Plugin | Adapter | Driver)[]>([])
  const nowPage = ref(1)
  const totalPage = ref(1)
  const totalItem = ref(0)
  const viewModule = ref<ModuleType>('plugin')
  const isRequesting = ref(false)

  const clear = () => {
    searchInput.value = ''
    searchTags.value = []
    storeData.value = []
    nowPage.value = 1
    totalPage.value = 1
    totalItem.value = 0
  }

  const isTagExisted = (tag: nb_cli_plugin_webui__app__models__store__SearchTag) => {
    return searchTags.value.some((t) => t.label === tag.label && t.text === tag.text)
  }

  const removeTag = (tag: nb_cli_plugin_webui__app__models__store__SearchTag) => {
    const index = searchTags.value.findIndex((t) => t.label === tag.label && t.text === tag.text)
    if (index !== -1) {
      searchTags.value.splice(index, 1)
    }
  }

  const updateTag = (tag: nb_cli_plugin_webui__app__models__store__SearchTag) => {
    if (isTagExisted(tag)) {
      removeTag(tag)
    } else {
      searchTags.value.push(tag)
    }
  }

  const updateData = async (projectID: string, isShowAll: boolean) => {
    isRequesting.value = true
    const isSearch = searchInput.value !== '' || searchTags.value.length > 0
    const { data, error } = await StoreService.getNonebotStoreItemsV1StoreNonebotListGet({
      query: {
        module_type: viewModule.value,
        page: nowPage.value,
        is_search: isSearch,
        show_all: isShowAll,
        project_id: projectID
      }
    })

    if (error) {
      toast.add('error', `获取商店数据失败，原因：${getErrorMessage(error)}`, '', 5000)
      isRequesting.value = false
      return
    }

    if (data) {
      storeData.value = data.detail
      totalPage.value = data.total_page
      totalItem.value = data.total_item
    }

    isRequesting.value = false
  }

  const selectModule = async (module: ModuleType, projectID: string) => {
    viewModule.value = module
    clear()
    await updateData(projectID, false)
  }

  const turnPage = async (page: number, projectID: string) => {
    nowPage.value = page >= 0 ? page : 0

    if (page >= totalPage.value) {
      nowPage.value = totalPage.value
    }
    await updateData(projectID, false)
  }

  const upDataBySearch = async (projectID: string) => {
    if (!projectID) {
      toast.add('info', '未选择实例，暂不支持搜索，已切换为商店浏览模式。', '', 3000)
      await updateData('', true)
      return
    }

    isRequesting.value = true
    const { data, error } = await StoreService.searchNonebotStoreItemV1StoreNonebotSearchPost({
      query: {
        project_id: projectID
      },
      body: {
        data: {
          module_type: viewModule.value,
          tags: searchTags.value,
          content: searchInput.value
        }
      }
    })

    if (error) {
      toast.add('error', `搜索失败，原因：${getErrorMessage(error)}`, '', 5000)
      isRequesting.value = false
      return
    }

    if (data) {
      nowPage.value = 1
      storeData.value = data.detail
      totalPage.value = data.total_page
      totalItem.value = data.total_item
    }

    isRequesting.value = false
  }

  return {
    searchInput,
    searchTags,
    storeData,
    nowPage,
    totalPage,
    totalItem,
    viewModule,
    isRequesting,
    clear,
    isTagExisted,
    removeTag,
    updateTag,
    updateData,
    selectModule,
    turnPage,
    upDataBySearch
  }
})
