<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const rows = ref([])
const err = ref('')
onMounted(async () => {
  try { rows.value = await getJSON('/api/quarantine') }
  catch (e) { err.value = String(e.message || e) }
})
</script>
<template>
  <div class="page">
    <header>
      <h1>隔离区</h1>
      <p class="muted">error 规则命中的行，不得进入精选区</p>
    </header>
    <p v-if="err" class="tag danger">{{ err }}</p>
    <div class="panel">
      <table>
        <thead><tr><th>ID</th><th>批次</th><th>数据集</th><th>行号</th><th>键</th><th>原因</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td>{{ r.id }}</td>
            <td>{{ r.batch_id }}</td>
            <td>{{ r.dataset_id }}</td>
            <td>{{ r.row_no }}</td>
            <td>{{ r.entity_key }}</td>
            <td class="muted">{{ r.reason }}</td>
            <td>{{ r.created_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
