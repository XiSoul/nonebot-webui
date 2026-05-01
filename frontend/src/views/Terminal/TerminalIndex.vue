<script setup lang="ts">
import OperationBar from '@/views/Operation/OperationBar.vue'
import TerminalItem from '@/views/Operation/TerminalItem.vue'
</script>

<template>
  <div class="flex flex-col gap-4">
    <OperationBar />

    <div class="p-4 rounded-box bg-base-200 text-sm leading-6">
      这里是独立维护终端。停止态下发送的项目命令会在实例目录中通过常驻 shell 执行，适合手动运行
      <span class="font-mono">python -m pip install</span>、
      <span class="font-mono">python -m playwright install chromium</span>、
      <span class="font-mono">nb run</span>
      等命令；实例运行时也可以并行执行维护命令，不会再和实例运行日志混在同一个面板里。
    </div>

    <TerminalItem mode="shell" />
  </div>
</template>
