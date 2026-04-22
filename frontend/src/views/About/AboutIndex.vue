<script setup lang="ts">
const repoUrl = 'https://github.com/XiSoul/nonebot-webui'
const readmeUrl = `${repoUrl}#readme`
const releaseUrl = `${repoUrl}/releases`
const dockerDocUrl = `${repoUrl}/blob/main/README.md#生产部署`

const features = [
  '面向 NoneBot 实例的创建、导入、运行、终端与文件管理',
  '支持 Docker 场景部署、代理与镜像源配置',
  '支持扩展安装、版本检查、更新与日志排查',
  '适合 NAS、WSL 和常驻容器环境的日常运维'
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
    description: '查看安装、导入已有实例、Docker 部署和常见说明。',
    href: readmeUrl,
    action: '打开 README'
  },
  {
    title: '更新文档',
    description: '查看版本发布记录、变更说明和后续升级参考。',
    href: releaseUrl,
    action: '查看 Releases'
  },
  {
    title: 'Docker 部署说明',
    description: '直接查看镜像、映射目录和生产部署示例。',
    href: dockerDocUrl,
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

    <section class="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
      <div class="rounded-[24px] border border-base-content/10 bg-base-200/80 p-6">
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

      <div class="rounded-[24px] border border-base-content/10 bg-base-200/80 p-6">
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
