<script setup lang="ts">
import { ProjectService } from '@/client/api'
import { ref } from 'vue'
import { useAddBotStore } from '.'

const store = useAddBotStore()

const inputValue = ref('')

const search = async () => {
  if (!inputValue.value) {
    store.warningMessage = '请输入实例路径'
    return
  }

  const { data, error } = await ProjectService.checkProjectTomlV1ProjectCheckTomlPost({
    query: {
      project_dir: inputValue.value
    }
  })
  if (error) {
    store.warningMessage = error.detail?.toString() ?? ''
  }

  if (data) {
    const detail = data.detail
    store.projectName = detail.project_name
    store.adapters = detail.adapters
    store.plugins = detail.plugins
    store.pluginDirs = detail.plugin_dirs
    store.builtinPlugins = detail.builtin_plugins
    store.projectPath = inputValue.value

    store.searchBotSuccess = true
    store.warningMessage = ''
    inputValue.value = ''
  }
}
</script>

<template>
  <div class="flex flex-col items-center gap-8">
    <div v-if="!store.searchBotSuccess" class="flex flex-col justify-center gap-4 w-full max-w-xs">
      <div class="form-control">
        <div class="label">
          <span class="label-text">实例绝对路径</span>
        </div>
        <input
          v-model="inputValue"
          type="text"
          placeholder="请输入"
          class="input input-bordered w-full max-w-xs"
          required
        />
        <div class="label">
          <span class="label-text-alt leading-5">
            Docker 或容器部署时，这里要填写容器内的绝对路径，例如
            <span class="font-mono">/external-projects/3998382152</span>，不是宿主机路径。
          </span>
        </div>
      </div>

      <button class="btn btn-primary text-base-100" @click="search()">开始扫描</button>
    </div>
    <div v-else class="flex flex-col justify-center gap-2 w-full">
      <div class="flex gap-4 rounded-lg p-4 bg-base-200">
        <span class="font-semibold">实例名称:</span>
        {{ store.projectName }}
      </div>

      <div
        :class="{
          'flex gap-4 rounded-lg p-4 bg-base-200': true,
          'opacity-50': !store.adapters.length
        }"
      >
        <span class="font-semibold">
          {{ store.adapters.length ? '已有适配器:' : '未找到适配器' }}
        </span>
        <div class="flex items-center flex-wrap gap-2">
          <span
            v-for="adapter in store.adapters"
            :key="adapter.name"
            role="button"
            class="badge badge-lg !bg-base-100"
          >
            {{ adapter.name }}
          </span>
        </div>
      </div>

      <div
        :class="{
          'flex gap-4 rounded-lg p-4 bg-base-200': true,
          'opacity-50': !store.plugins.length
        }"
      >
        <span class="font-semibold">
          {{ store.plugins.length ? '已有插件:' : '未找到插件' }}
        </span>
        <div class="flex items-center flex-wrap gap-2">
          <span
            v-for="plugin in store.plugins"
            :key="plugin"
            role="button"
            class="badge badge-lg !bg-base-100"
          >
            {{ plugin }}
          </span>
        </div>
      </div>

      <div class="flex flex-col gap-2 rounded-lg p-4 bg-base-200">
        <span class="font-semibold">
          {{ store.pluginDirs.length ? '已有插件目录:' : '未配置插件目录' }}
        </span>
        <div v-if="store.pluginDirs.length" class="flex items-center flex-wrap gap-2">
          <span
            v-for="plugin_dir in store.pluginDirs"
            :key="plugin_dir"
            role="button"
            class="badge badge-lg !bg-base-100"
          >
            {{ plugin_dir }}
          </span>
        </div>
        <span v-else class="text-sm opacity-70">
          当前项目没有在配置里声明 <span class="font-mono">plugin_dirs</span>，这不影响继续导入；
          已安装插件仍会按项目配置读取。
        </span>
      </div>
    </div>

    <div class="w-full flex items-center">
      <button
        v-if="store.searchBotSuccess"
        class="btn btn-sm"
        @click="(store.searchBotSuccess = false), store.reset()"
      >
        重新扫描
      </button>

      <div class="w-full"></div>

      <div class="shrink-0 flex items-center gap-2">
        <form method="dialog">
          <button class="btn btn-sm">取消</button>
        </form>

        <button
          :class="{
            'btn btn-sm btn-primary text-base-100': true,
            'btn-disabled': !store.searchBotSuccess
          }"
          @click="store.step++"
        >
          下一步
        </button>
      </div>
    </div>
  </div>
</template>
