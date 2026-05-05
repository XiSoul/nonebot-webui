<script setup lang="ts">
import OperationBar from '@/views/Operation/OperationBar.vue'
import TerminalItem from '@/views/Operation/TerminalItem.vue'
</script>

<template>
  <div class="flex flex-col gap-4">
    <OperationBar />

    <div class="rounded-[28px] border border-base-content/10 bg-base-200 px-5 py-4 text-sm leading-7 shadow-sm">
      <div class="text-xs uppercase tracking-[0.24em] text-base-content/45">Maintenance Terminal</div>
      <div class="mt-2 text-base-content/78">
        这里是独立维护终端。停止态下发送的项目命令会在实例目录中通过常驻 shell 执行，适合手动运行
        <span class="font-mono">python -m pip install</span>、
        <span class="font-mono">python -m playwright install chromium</span>、
        <span class="font-mono">nb run</span>
        等命令；实例运行时也可以并行执行维护命令，不会再和实例运行日志混在同一个面板里。
      </div>
    </div>

    <TerminalItem mode="shell" />
  </div>
</template>
