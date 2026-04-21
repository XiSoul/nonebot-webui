<script setup lang="ts">
import OperationBar from '@/views/Operation/OperationBar.vue'
import TerminalItem from '@/views/Operation/TerminalItem.vue'
</script>

<template>
  <div class="flex flex-col gap-4">
    <OperationBar />

    <div class="p-4 rounded-box bg-base-200 text-sm leading-6">
      停止态下发送的项目命令会在实例目录中通过 shell 执行，适合手动运行
      <span class="font-mono">python -m pip install</span>、
      <span class="font-mono">python -m playwright install chromium</span>、
      <span class="font-mono">nb run</span>
      等命令。
    </div>

    <TerminalItem />
  </div>
</template>
