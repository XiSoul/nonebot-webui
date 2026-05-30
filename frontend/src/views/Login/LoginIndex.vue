<script setup lang="ts">
import LoginForm from '@/views/Login/LoginForm.vue'
import Footer from '@/components/FooterItem.vue'
</script>

<template>
  <div class="hero min-h-screen">
    <div class="hero-content text-center flex-col">
      <span class="material-symbols-outlined text-primary" style="font-size: 14rem"> circle </span>

      <h1 class="text-5xl font-normal"><span class="text-primary">None</span>Bot</h1>
      <p class="text-base-content opacity-60 text-xs tracking-wide">
        忘记密码？执行 <code class="bg-base-200 px-1.5 py-0.5 rounded text-[11px]">docker exec -it nonebot-webui python -m nb_cli_plugin_webui.scripts reset_token</code> 重置
      </p>

      <LoginForm />
    </div>
  </div>

  <Footer />
</template>

<style scoped>
.material-symbols-outlined {
  font-variation-settings:
    'FILL' 0,
    'wght' 50,
    'GRAD' -25,
    'opsz' 20;
}
</style>
