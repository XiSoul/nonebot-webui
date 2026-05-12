<script setup lang="ts">
// TODO: 优化组件使用体验

import { ref } from 'vue'

const isShow = ref(false)
defineExpose({
  showDrawer: () => {
    isShow.value = true
  },
  hiddenDrawer: () => {
    hiddenDrawer()
  }
})

const hiddenDrawer = () => {
  isShow.value = false
}
</script>

<template>
  <slot name="button"></slot>

  <Teleport to="body">
    <div v-if="isShow" class="fixed inset-0 z-[2000]">
      <Transition class="invisible md:visible">
        <div
          role="button"
          class="absolute inset-0 bg-gray-500/50"
          @click="hiddenDrawer"
        ></div>
      </Transition>

      <div
        class="absolute top-0 right-0 h-screen nb-sidebar-surface shadow-2xl shrink-0 flex flex-col w-full sm:w-[28rem] xl:w-[32rem] 2xl:w-[36rem] max-w-full"
      >
        <!-- Drawer Header -->
        <div class="nb-header-surface h-16 px-6 shrink-0 flex items-center justify-between">
          <span class="text-xl font-semibold">
            <slot name="drawer-title"></slot>
          </span>
          <div class="btn btn-sm btn-square btn-ghost" @click="hiddenDrawer">
            <span class="material-symbols-outlined"> arrow_forward_ios </span>
          </div>
        </div>

        <div class="bg-base-content/10 h-px"></div>

        <div class="flex h-full flex-col overflow-y-auto overflow-x-hidden px-6 py-4">
          <!-- Drawer Body -->
          <slot name="drawer-body"></slot>
        </div>

        <!-- Drawer Footer -->
        <slot name="drawer-footer"></slot>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.v-enter-active,
.v-leave-active {
  transition: opacity 150ms ease;
}

.v-enter-from,
.v-leave-to {
  opacity: 0;
}

.material-symbols-outlined {
  font-variation-settings:
    'FILL' 0,
    'wght' 300,
    'GRAD' 0,
    'opsz' 24;
}
</style>
