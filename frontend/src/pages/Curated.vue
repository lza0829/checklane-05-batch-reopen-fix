<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const rows = ref([])
const err = ref('')
onMounted(async () => {
  try { rows.value = await getJSON('/api/curated') }
  catch (e) { err.value = String(e.message || e) }
})
</script>
<template>
  <div class="page">
    <header>
      <h1>精选区</h1>
      <p class="muted">通过入检并签发的行；同键再次签发会覆盖</p>
    </header>
    <p v-if="err" class="tag danger">{{ err }}</p>
    <div class="panel">
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
        </tbody>
      </table>
    </div>
  </div>
</template>
