<script setup lang="ts">
import { ProjectService } from '@/client/api'
import { computed, ref } from 'vue'
import { useAddBotStore } from '.'

const store = useAddBotStore()

const inputValue = ref('')
const discoveredOnlyPluginDirs = computed(() =>
  store.discoveredPluginDirs.filter((dir) => !store.pluginDirs.includes(dir))
)

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
    store.discoveredPluginDirs = detail.discovered_plugin_dirs ?? []
    store.builtinPlugins = detail.builtin_plugins
    store.projectPath = detail.resolved_project_dir || inputValue.value

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
          <span class="label-text">实例路径</span>
        </div>
        <input
          v-model="inputValue"
          type="text"
          placeholder="如 3998382152 或 /external-projects/3998382152"
          class="input input-bordered w-full max-w-xs"
          required
        />
        <div class="label">
          <span class="label-text-alt leading-5">
            现在支持相对路径和容器内绝对路径，例如
            <span class="font-mono">3998382152</span>、
            <span class="font-mono">external-projects/3998382152</span>、
            <span class="font-mono">/external-projects/3998382152</span>。
            如果是 Docker 部署，依然不能填写 NAS 或宿主机自己的真实路径。
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

      <div class="flex gap-4 rounded-lg p-4 bg-base-200">
        <span class="font-semibold">实际项目路径:</span>
        <span class="font-mono break-all">{{ store.projectPath }}</span>
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
          {{ store.plugins.length ? '已配置插件:' : '未配置插件' }}
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
        <span v-if="!store.plugins.length" class="text-sm opacity-70">
          这里显示的是 <span class="font-mono">tool.nonebot.plugins</span> 里声明的插件；
          大多数通过 pip 安装的插件本体都在项目的
          <span class="font-mono">.venv/site-packages</span> 中，而不是本地插件目录。
        </span>
      </div>

      <div class="flex flex-col gap-2 rounded-lg p-4 bg-base-200">
        <span class="font-semibold">
          {{ store.pluginDirs.length ? '已声明本地插件目录:' : '未声明本地插件目录' }}
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
          当前项目没有在 <span class="font-mono">tool.nonebot.plugin_dirs</span> 中声明本地插件目录。
          这不影响继续导入，也不代表项目没有安装插件。
        </span>
      </div>

      <div
        :class="{
          'flex flex-col gap-2 rounded-lg p-4 bg-base-200': true,
          'opacity-50': !discoveredOnlyPluginDirs.length
        }"
      >
        <span class="font-semibold">
          {{ discoveredOnlyPluginDirs.length ? '扫描到的候选本地插件目录:' : '未扫描到额外候选目录' }}
        </span>
        <div v-if="discoveredOnlyPluginDirs.length" class="flex items-center flex-wrap gap-2">
          <span
            v-for="plugin_dir in discoveredOnlyPluginDirs"
            :key="plugin_dir"
            role="button"
            class="badge badge-lg !bg-base-100"
          >
            {{ plugin_dir }}
          </span>
        </div>
        <span v-if="discoveredOnlyPluginDirs.length" class="text-sm opacity-70">
          这些目录是根据常见目录结构自动识别出来的，仅供你核对；
          它们当前并不等于项目已经声明的 <span class="font-mono">plugin_dirs</span> 配置。
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
