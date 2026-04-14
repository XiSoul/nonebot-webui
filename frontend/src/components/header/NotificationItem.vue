<script setup lang="ts">
import { computed, ref } from 'vue'

import DrawerItem from '@/components/DrawerItem.vue'
import { useToastStore } from '@/stores'

const store = useToastStore()
const drawerRef = ref<InstanceType<typeof DrawerItem> | null>(null)

const expandedIds = ref<Record<string, boolean>>({})

const iconName = (type: string) => {
  if (type === 'success') return 'check_circle'
  if (type === 'error') return 'cancel'
  if (type === 'warning') return 'error'
  return 'info'
}

const iconClass = (type: string) => {
  if (type === 'success') return 'text-success'
  if (type === 'error') return 'text-error'
  if (type === 'warning') return 'text-warning'
  return 'text-info'
}

const detailText = (toast: { message: string; detail?: string }) => {
  return toast.detail ? `${toast.message} ${toast.detail}` : toast.message
}

const shouldShowExpand = (toast: { message: string; detail?: string }) => {
  return detailText(toast).length > 64
}

const toggleExpanded = (id: string) => {
  expandedIds.value[id] = !expandedIds.value[id]
}

const hasToasts = computed(() => store.toasts.length > 0)
</script>

<template>
  <DrawerItem ref="drawerRef">
    <template v-slot:button>
      <button class="btn btn-sm btn-ghost btn-square" @click="drawerRef?.showDrawer()">
        <div class="indicator">
          <span
            v-if="store.toasts.length"
            class="indicator-item badge badge-primary font-normal text-base-100"
          >
            {{ store.toasts.length }}
          </span>
          <span class="material-symbols-outlined"> notifications </span>
        </div>
      </button>
    </template>

    <template v-slot:drawer-title>消息列表</template>

    <template v-slot:drawer-body>
      <div v-if="hasToasts" class="grid gap-2">
        <div
          v-for="toast in store.toasts"
          :key="toast.id"
          :class="[
            'rounded-lg bg-base-200/60 hover:bg-base-200 transition-colors p-4 flex gap-3',
            expandedIds[toast.id] ? 'items-start min-h-[108px]' : 'items-start h-[108px] overflow-hidden'
          ]"
        >
          <span class="material-symbols-outlined text-3xl shrink-0" :class="iconClass(toast.type)">
            {{ iconName(toast.type) }}
          </span>

          <div class="min-w-0 flex-1 flex flex-col gap-2">
            <div class="flex items-start gap-2">
              <div class="min-w-0 flex-1">
                <p
                  :class="expandedIds[toast.id] ? 'break-all whitespace-pre-wrap' : 'notification-preview'"
                >
                  {{ detailText(toast) }}
                </p>
                <button
                  v-if="shouldShowExpand(toast)"
                  class="text-xs text-error mt-1"
                  @click="toggleExpanded(toast.id)"
                >
                  {{ expandedIds[toast.id] ? '收起详情' : '查看详情' }}
                </button>
              </div>

              <button
                class="btn btn-sm btn-square btn-ghost font-normal shrink-0"
                @click="store.remove(toast.id)"
              >
                <span class="material-symbols-outlined"> close </span>
              </button>
            </div>

            <div class="text-xs text-base-content/50">
              {{ new Date(toast.createdAt).toLocaleString() }}
            </div>
          </div>
        </div>
      </div>
      <div v-else class="text-center">暂无消息</div>
    </template>

    <template v-slot:drawer-footer>
      <div v-if="hasToasts">
        <div class="bg-base-content/10 h-px"></div>
        <button class="w-full rounded-none btn btn-lg btn-ghost" @click="store.clear()">
          清除所有
        </button>
      </div>
    </template>
  </DrawerItem>
</template>

<style scoped>
.material-symbols-outlined {
  font-variation-settings:
    'FILL' 0,
    'wght' 400,
    'GRAD' -25,
    'opsz' 48;
}

.notification-preview {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  word-break: break-word;
}
</style>
