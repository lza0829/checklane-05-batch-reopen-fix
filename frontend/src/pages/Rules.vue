<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, patchJSON } from '../api'
const rows = ref([])
const err = ref('')
async function load() {
  rows.value = await getJSON('/api/rules')
}
async function toggle(r) {
  await patchJSON(`/api/rules/${r.id}`, { enabled: !r.enabled })
  await load()
}
onMounted(async () => {
  try { await load() }
  catch (e) { err.value = String(e.message || e) }
})
</script>
<template>
  <div class="page">
    <header>
      <h1>规则</h1>
      <p class="muted">字段级必填 / 类型检查；error 进隔离，warn 仍可放行</p>
    </header>
    <p v-if="err" class="tag danger">{{ err }}</p>
    <div class="panel">
      <table>
        <thead><tr><th>ID</th><th>数据集</th><th>名称</th><th>字段</th><th>类型</th><th>严重度</th><th>启用</th><th></th></tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td>{{ r.id }}</td>
            <td>{{ r.dataset_id }}</td>
            <td>{{ r.name }}</td>
            <td><code>{{ r.field }}</code></td>
            <td>{{ r.rule_type }}</td>
            <td><span class="tag" :class="r.severity === 'error' ? 'danger' : ''">{{ r.severity }}</span></td>
            <td>{{ r.enabled ? '是' : '否' }}</td>
            <td><button @click="toggle(r)">{{ r.enabled ? '停用' : '启用' }}</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
