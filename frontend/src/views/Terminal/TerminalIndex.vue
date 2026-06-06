<script setup lang="ts">
import OperationBar from '@/views/Operation/OperationBar.vue'
import TerminalItem from '@/views/Operation/TerminalItem.vue'
</script>

<template>
  <div class="nb-page">
    <OperationBar />

    <section class="nb-page-heading">
      <div>
        <p class="nb-kicker">Maintenance Terminal</p>
        <h1 class="text-2xl font-semibold tracking-tight text-base-content">维护终端</h1>
        <p class="mt-2 max-w-3xl text-sm leading-7 text-base-content/65">
          独立执行实例维护命令，适合安装依赖、修复环境或手动运行调试命令，不会和实例运行日志混在同一个面板里。
        </p>
      </div>
    </section>

    <section class="nb-panel-surface rounded-[28px] px-5 py-4 text-sm leading-7">
      <div class="nb-kicker">Shell Workflow</div>
      <div class="mt-2 text-base-content/78">
        停止态下发送的项目命令会在实例目录中通过常驻 shell 执行，适合手动运行
        <span class="font-mono">python -m pip install</span>、
        <span class="font-mono">python -m playwright install chromium</span>、
        <span class="font-mono">nb run</span>
        等命令；实例运行时也可以并行执行维护命令。
      </div>
    </section>

    <section class="nb-panel-surface overflow-hidden rounded-[28px] p-0">
      <TerminalItem mode="shell" />
    </section>
  </div>
</template>
