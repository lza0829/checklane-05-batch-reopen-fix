<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const rows = ref([])
const err = ref('')
onMounted(async () => {
  try { rows.value = await getJSON('/api/datasets') }
  catch (e) { err.value = String(e.message || e) }
})
</script>
<template>
  <div class="page">
    <header>
      <h1>数据集</h1>
      <p class="muted">登记本机夹具路径，作为入检源</p>
    </header>
    <p v-if="err" class="tag danger">{{ err }}</p>
    <div class="panel">
      <table>
        <thead><tr><th>ID</th><th>名称</th><th>夹具</th><th>类型</th><th>启用</th><th>备注</th></tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td>{{ r.id }}</td>
            <td>{{ r.name }}</td>
            <td><code>{{ r.fixture_path }}</code></td>
            <td>{{ r.entity_type }}</td>
            <td><span class="tag" :class="r.enabled ? 'ok' : ''">{{ r.enabled ? '是' : '否' }}</span></td>
            <td class="muted">{{ r.note }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
