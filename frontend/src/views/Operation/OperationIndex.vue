<script setup lang="ts">
import OperationBar from '@/views/Operation/OperationBar.vue'
import BotDetails from '@/views/Operation/BotDetails.vue'
import TerminalItem from '@/views/Operation/TerminalItem.vue'
</script>

<template>
  <div class="flex flex-col gap-6 pb-6">
    <OperationBar />
    <div class="grid grid-cols-1 items-start gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1.08fr)]">
      <BotDetails />
      <TerminalItem mode="runtime" />
    </div>
  </div>
</template>
