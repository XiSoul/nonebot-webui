<script setup lang="ts">
import { computed, ref } from 'vue'
import { useCustomStore } from '@/stores'
import DrawerItem from '@/components/DrawerItem.vue'

const store = useCustomStore()

const drawerRef = ref<InstanceType<typeof DrawerItem> | null>()

const selectedPreset = computed({
  get: () => store.currentThemePreset,
  set: (value) => store.setThemePreset(value)
})

const selectedAccent = computed({
  get: () => store.currentThemeAccent,
  set: (value) => store.setThemeAccent(value)
})
</script>

<template>
  <DrawerItem ref="drawerRef">
    <template v-slot:button>
      <button class="btn btn-sm btn-ghost btn-square" @click="drawerRef?.showDrawer()">
        <span class="material-symbols-outlined"> tune </span>
      </button>
    </template>

    <template v-slot:drawer-title>WebUI 设置</template>

    <template v-slot:drawer-body>
      <div class="flex flex-col gap-6">
        <section class="space-y-3">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="font-medium">界面主题</div>
              <div class="text-xs opacity-60 mt-1">
                像 hermes-web-ui 一样切换不同界面风格。
              </div>
            </div>
            <span class="badge badge-outline">{{ store.currentThemePreset }}</span>
          </div>

          <div class="grid gap-3">
            <label
              v-for="item in store.themePresetOptions"
              :key="item.id"
              class="nb-panel-surface cursor-pointer rounded-2xl p-4 transition-colors hover:border-primary/40 hover:bg-base-200/60"
              :class="selectedPreset === item.id ? 'border-primary bg-primary/5' : ''"
            >
              <input v-model="selectedPreset" type="radio" class="sr-only" :value="item.id" />
              <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div class="min-w-0 flex-1">
                  <div class="font-medium">{{ item.label }}</div>
                  <div class="text-xs opacity-70 mt-1">{{ item.description }}</div>
                  <div
                    class="mt-3 h-20 rounded-2xl border border-base-content/10 p-3"
                    :style="{
                      background: `linear-gradient(135deg, ${item.preview[0]} 0%, ${item.preview[1]} 58%, ${item.preview[2]} 100%)`
                    }"
                  >
                    <div class="flex h-full items-end justify-between">
                      <span class="h-2.5 w-16 rounded-full bg-white/70"></span>
                      <span class="h-8 w-8 rounded-xl bg-white/35 backdrop-blur-sm"></span>
                    </div>
                  </div>
                </div>
                <div class="flex items-center gap-1 self-start sm:self-auto">
                  <span
                    v-for="color in item.preview"
                    :key="color"
                    class="h-4 w-4 rounded-full border border-base-content/10"
                    :style="{ backgroundColor: color }"
                  ></span>
                </div>
              </div>
            </label>
          </div>
        </section>

        <section class="space-y-3">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="font-medium">主题配色</div>
              <div class="text-xs opacity-60 mt-1">
                切换按钮、强调色和主要操作色。
              </div>
            </div>
            <span class="badge badge-primary text-base-100">{{ store.currentThemeAccent }}</span>
          </div>

          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label
              v-for="item in store.themeAccentOptions"
              :key="item.id"
              class="nb-panel-surface cursor-pointer rounded-2xl p-3 transition-colors hover:border-primary/40"
              :class="selectedAccent === item.id ? 'border-primary bg-primary/10' : ''"
            >
              <input v-model="selectedAccent" type="radio" class="sr-only" :value="item.id" />
              <div class="flex items-center gap-3">
                <span
                  class="inline-flex h-8 w-8 shrink-0 rounded-xl border border-base-content/10 shadow-sm"
                  :style="{ backgroundColor: item.color }"
                ></span>
                <div class="min-w-0">
                  <div class="font-medium">{{ item.label }}</div>
                  <div class="text-[11px] opacity-60">{{ item.color }}</div>
                </div>
              </div>
            </label>
          </div>
        </section>

        <section class="nb-panel-surface space-y-3 rounded-2xl p-4">
          <div class="font-medium">亮暗模式</div>
          <div class="form-control">
            <label class="label cursor-pointer px-0">
              <span class="label-text">主题跟随系统</span>
              <input
                type="checkbox"
                class="toggle"
                :checked="store.isThemeFollowSystem"
                @click="store.toggleThemeFollowSystem"
              />
            </label>
          </div>

          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <button
              class="btn"
              :class="store.currentTheme === 'light' ? 'btn-primary text-base-100' : 'btn-outline'"
              @click="store.toggleTheme('light')"
            >
              亮色
            </button>
            <button
              class="btn"
              :class="store.currentTheme === 'dark' ? 'btn-primary text-base-100' : 'btn-outline'"
              @click="store.toggleTheme('dark')"
            >
              暗色
            </button>
          </div>
        </section>

        <section class="nb-panel-surface space-y-3 rounded-2xl p-4">
          <div class="font-medium">其它设置</div>

          <div class="form-control">
            <label class="label cursor-pointer px-0">
              <span class="label-text">启用开发模式</span>
              <input
                type="checkbox"
                class="toggle"
                :checked="store.isDebug"
                @click="store.toggleDebug"
              />
            </label>
          </div>

          <div class="form-control">
            <label class="label cursor-pointer px-0">
              <span class="label-text">是否即时搜索</span>
              <input
                type="checkbox"
                class="toggle"
                :checked="store.isInstantSearch"
                @click="store.toggleInstantSearch()"
              />
            </label>
          </div>
        </section>
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
</style>
