<script setup>
</script>
<template>
  <div class="layout">
    <aside class="side">
      <h1>Checklane</h1>
      <p>检道 · 质检放行</p>
      <nav>
        <router-link to="/">总览</router-link>
        <router-link to="/datasets">数据集</router-link>
        <router-link to="/rules">规则</router-link>
        <router-link to="/inspect">入检台</router-link>
        <router-link to="/batches">批次</router-link>
        <router-link to="/quarantine">隔离区</router-link>
        <router-link to="/curated">精选区</router-link>
      </nav>
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>
