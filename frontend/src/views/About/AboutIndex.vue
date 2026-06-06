<script setup lang="ts">
const repoUrl = 'https://github.com/XiSoul/nonebot-webui'
const branchName = 'master'
const usageDocUrl = `${repoUrl}/blob/${branchName}/docs/USAGE.md`
const updateDocUrl = `${repoUrl}/blob/${branchName}/docs/UPDATE.md`
const deployDocUrl = `${repoUrl}/blob/${branchName}/docs/DEPLOY.md`
const qqGroup = '306146537'

const features = [
  '面向 NoneBot 实例的创建、导入、运行、终端与文件管理',
  '支持 Docker 场景部署、代理与镜像源配置',
  '支持扩展安装、版本检查、更新与日志排查',
  '适合 NAS、WSL 和常驻容器环境的日常运维'
]

const communityCards = [
  {
    title: 'QQ 交流群',
    description: '部署、更新、使用或扩展开发遇到问题，欢迎加入群聊交流。',
    icon: 'groups',
    value: qqGroup
  }
]

const docs = [
  {
    title: '项目仓库',
    description: '查看源码、问题反馈和最新提交记录。',
    href: repoUrl,
    action: '打开 GitHub'
  },
  {
    title: '使用文档',
    description: '查看首次登录、页面说明、实例接入和常见使用问题。',
    href: usageDocUrl,
    action: '打开使用文档'
  },
  {
    title: '更新文档',
    description: '查看近期改动、升级关注点和发版建议。',
    href: updateDocUrl,
    action: '打开更新文档'
  },
  {
    title: '部署文档',
    description: '查看 Docker、NAS、WSL 场景下的部署和挂载说明。',
    href: deployDocUrl,
    action: '查看部署文档'
  }
]
</script>

<template>
  <div class="flex flex-col gap-6">
    <section
      class="overflow-hidden rounded-[28px] border border-base-content/10 bg-gradient-to-br from-base-200 via-base-100 to-base-200 p-8"
    >
      <div class="flex flex-col gap-5 lg:max-w-4xl">
        <div
          class="inline-flex w-fit items-center rounded-full border border-primary/20 bg-primary/10 px-4 py-1 text-sm text-primary"
        >
          About NoneBot WebUI
        </div>
        <div class="flex flex-col gap-3">
          <h1 class="text-3xl font-semibold tracking-tight md:text-4xl">关于项目</h1>
          <p class="max-w-3xl text-base leading-7 text-base-content/75">
            NoneBot WebUI 是一个围绕 NoneBot 项目管理和部署运维打造的可视化界面，重点覆盖实例导入、
            运行控制、依赖安装、扩展管理、日志查看和 Docker 部署等高频场景。
          </p>
        </div>
      </div>
    </section>

    <section
      class="nb-panel-surface relative overflow-hidden rounded-[28px] border border-primary/15 bg-primary/5 p-6"
    >
      <div class="absolute right-6 top-4 hidden text-[6rem] leading-none text-primary/10 md:block">
        QQ
      </div>
      <div class="relative flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div
          v-for="card in communityCards"
          :key="card.title"
          class="flex min-w-0 flex-1 items-start gap-4"
        >
          <span
            class="material-symbols-outlined shrink-0 rounded-2xl bg-primary/12 p-3 text-3xl text-primary ring-1 ring-primary/15"
          >
            {{ card.icon }}
          </span>
          <div class="min-w-0">
            <h2 class="text-xl font-semibold">{{ card.title }}</h2>
            <p class="mt-1 text-sm leading-6 text-base-content/70">
              {{ card.description }}
            </p>
          </div>
        </div>
        <div
          class="inline-flex w-fit shrink-0 items-center gap-2 rounded-2xl border border-primary/20 bg-base-100/80 px-4 py-3 text-primary shadow-sm shadow-primary/10"
        >
          <span class="text-sm font-medium text-base-content/60">群号</span>
          <span class="font-mono text-2xl font-bold tracking-wide">{{ qqGroup }}</span>
        </div>
      </div>
    </section>

    <section class="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
      <div class="nb-panel-surface rounded-[28px] border border-base-content/10 bg-base-200/80 p-6">
        <div class="mb-4 flex items-center gap-3">
          <span class="material-symbols-outlined text-primary">deployed_code</span>
          <h2 class="text-xl font-semibold">项目简介</h2>
        </div>
        <div class="grid gap-3">
          <div
            v-for="feature in features"
            :key="feature"
            class="rounded-2xl border border-base-content/10 bg-base-100/80 px-4 py-3 text-sm leading-6 text-base-content/80"
          >
            {{ feature }}
          </div>
        </div>
      </div>

      <div class="nb-panel-surface rounded-[28px] border border-base-content/10 bg-base-200/80 p-6">
        <div class="mb-4 flex items-center gap-3">
          <span class="material-symbols-outlined text-primary">newsmode</span>
          <h2 class="text-xl font-semibold">更新文档</h2>
        </div>
        <div class="grid gap-3">
          <a
            v-for="doc in docs"
            :key="doc.title"
            :href="doc.href"
            target="_blank"
            rel="noreferrer"
            class="group rounded-2xl border border-base-content/10 bg-base-100/80 px-4 py-4 transition hover:border-primary/30 hover:bg-base-100"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="flex flex-col gap-1">
                <div class="font-medium">{{ doc.title }}</div>
                <div class="text-sm leading-6 text-base-content/70">
                  {{ doc.description }}
                </div>
              </div>
              <span
                class="material-symbols-outlined text-base-content/40 transition group-hover:translate-x-1 group-hover:text-primary"
              >
                arrow_outward
              </span>
            </div>
            <div class="mt-3 text-sm text-primary">{{ doc.action }}</div>
          </a>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.material-symbols-outlined {
  font-variation-settings:
    'FILL' 0,
    'wght' 300,
    'GRAD' -25,
    'opsz' 48;
}
</style>
