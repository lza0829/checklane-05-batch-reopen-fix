<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const rows = ref([])
const withdrawn = ref([])
const err = ref('')
const tab = ref('active')
onMounted(async () => {
  try {
    rows.value = await getJSON('/api/curated')
    withdrawn.value = await getJSON('/api/curated/withdrawn')
  } catch (e) { err.value = String(e.message || e) }
})
async function switchTab(t) {
  tab.value = t
  err.value = ''
  try {
    if (t === 'active') rows.value = await getJSON('/api/curated')
    else withdrawn.value = await getJSON('/api/curated/withdrawn')
  } catch (e) { err.value = String(e.message || e) }
}
</script>
<template>
  <div class="page">
    <header>
      <h1>精选区</h1>
      <p class="muted">通过入检并签发的有效行（active）；重开撤回的行保留在审计视图，不再计入存量</p>
    </header>
    <p v-if="err" class="tag danger">{{ err }}</p>
    <div class="row" style="gap:8px; margin-bottom:12px">
      <button class="small" :class="tab === 'active' ? '' : 'muted'" @click="switchTab('active')">
        有效存量（{{ rows.length }}）
      </button>
      <button class="small" :class="tab === 'withdrawn' ? '' : 'muted'" @click="switchTab('withdrawn')">
        重开撤回审计（{{ withdrawn.length }}）
      </button>
    </div>
    <div class="panel" v-if="tab === 'active'">
      <table>
        <thead><tr><th>ID</th><th>数据集</th><th>批次</th><th>键</th><th>签发时间</th></tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td>{{ r.id }}</td>
            <td>{{ r.dataset_id }}</td>
            <td>{{ r.batch_id }}</td>
            <td>{{ r.entity_key }}</td>
            <td>{{ r.released_at }}</td>
          </tr>
          <tr v-if="!rows.length"><td colspan="5" class="muted">暂无有效行（批次重开后已撤回，再入检后按新结果恢复）</td></tr>
        </tbody>
      </table>
    </div>
    <div class="panel" v-else>
      <table>
        <thead>
          <tr><th>ID</th><th>数据集</th><th>原批次</th><th>键</th><th>原签发时间</th><th>撤回时间</th><th>撤回原因</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in withdrawn" :key="r.id">
            <td>{{ r.id }}</td>
            <td>{{ r.dataset_id }}</td>
            <td>{{ r.batch_id }}</td>
            <td>{{ r.entity_key }}</td>
            <td class="muted">{{ r.released_at }}</td>
            <td>{{ r.invalidated_at }}</td>
            <td class="muted">{{ r.invalidate_reason }}</td>
          </tr>
          <tr v-if="!withdrawn.length"><td colspan="7" class="muted">暂无撤回记录</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
