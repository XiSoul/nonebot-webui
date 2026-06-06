<script setup lang="ts">
import OperationBar from '@/views/Operation/OperationBar.vue'
import TerminalItem from '@/views/Operation/TerminalItem.vue'
</script>

<template>
  <div class="nb-page">
    <OperationBar />
    <section class="nb-page-heading">
      <div>
        <p class="nb-kicker">Runtime Control</p>
        <h1 class="text-2xl font-semibold tracking-tight text-base-content">实例操作</h1>
        <p class="mt-2 max-w-3xl text-sm leading-7 text-base-content/65">
          管理实例运行状态、观察启动输出和运行日志。这里是带主体功能的操作页，保留清晰状态和日志区域。
        </p>
      </div>
    </section>
    <TerminalItem mode="runtime" />
  </div>
</template>
