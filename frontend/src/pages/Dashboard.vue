<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const stats = ref(null)
const err = ref('')
onMounted(async () => {
  try { stats.value = await getJSON('/api/dashboard') }
  catch (e) { err.value = String(e.message || e) }
})
</script>
<template>
  <div class="page">
    <header>
      <h1>检道总览</h1>
      <p class="muted">入检批次 → 规则裁决 → 隔离/放行签发 → 清单对账</p>
    </header>
    <p v-if="err" class="tag danger">{{ err }}</p>
    <div class="tiles" v-if="stats">
      <div class="tile"><div class="hero-num">{{ stats.dataset_count }}</div><div class="muted">数据集</div></div>
      <div class="tile"><div class="hero-num">{{ stats.enabled_rule_count }}</div><div class="muted">启用规则</div></div>
      <div class="tile"><div class="hero-num">{{ stats.batch_count }}</div><div class="muted">入检批次</div></div>
      <div class="tile"><div class="hero-num">{{ stats.curated_count }}</div><div class="muted">精选行</div></div>
      <div class="tile"><div class="hero-num">{{ stats.quarantine_count }}</div><div class="muted">隔离行</div></div>
    </div>
    <router-link class="btn" to="/inspect">去入检台</router-link>
  </div>
</template>
