<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON } from '../api'
const rows = ref([])
const detail = ref(null)
const err = ref('')
const busyId = ref(null)
const reopenReason = ref('')
const showReasonBox = ref(null)

async function load() {
  rows.value = await getJSON('/api/batches')
}
async function show(id) {
  detail.value = await getJSON(`/api/batches/${id}`)
}
function toggleReason(id) {
  showReasonBox.value = showReasonBox.value === id ? null : id
  reopenReason.value = ''
  err.value = ''
}
async function reopen(id) {
  const reason = reopenReason.value.trim()
  if (!reason) {
    err.value = '请填写重开原因'
    return
  }
  busyId.value = id
  err.value = ''
  try {
    detail.value = await postJSON(`/api/batches/${id}/reopen`, { reason })
    showReasonBox.value = null
    reopenReason.value = ''
    await load()
  } catch (e) {
    err.value = String(e.message || e)
  } finally {
    busyId.value = null
  }
}
async function reinspect(id) {
  busyId.value = id
  err.value = ''
  try {
    const next = await postJSON('/api/inspect/reopen-round', {
      dataset_id: detail.value.dataset_id,
      reopen_from_batch_id: id,
    })
    detail.value = await getJSON(`/api/batches/${next.id}`)
    await load()
  } catch (e) {
    err.value = String(e.message || e)
  } finally {
    busyId.value = null
  }
}
function statusClass(s) {
  if (s === 'released') return 'ok'
  if (s === 'reopened') return 'warn'
  return ''
}
onMounted(async () => {
  try { await load() }
  catch (e) { err.value = String(e.message || e) }
})
</script>
<template>
  <div class="page">
    <header>
      <h1>批次</h1>
      <p class="muted">历史入检批次与报告；已签发批次可重开撤回并再入检</p>
    </header>
    <p v-if="err" class="tag danger">{{ err }}</p>
    <div class="panel">
      <table>
        <thead>
          <tr><th>ID</th><th>数据集</th><th>状态</th><th>轮次</th><th>扫描</th><th>通过</th><th>隔离</th><th>签发</th><th>时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          <template v-for="r in rows" :key="r.id">
            <tr style="cursor:pointer" @click="show(r.id)">
              <td>{{ r.id }}</td>
              <td>{{ r.dataset_id }}</td>
              <td><span class="tag" :class="statusClass(r.status)">{{ r.status }}</span></td>
              <td>R{{ r.round_no }}<span v-if="r.reopened_from_id" class="muted">（重开自 #{{ r.reopened_from_id }}）</span></td>
              <td>{{ r.scanned_count }}</td>
              <td>{{ r.passed_count }}</td>
              <td>{{ r.quarantined_count }}</td>
              <td>{{ r.released_count }}</td>
              <td>{{ r.created_at }}</td>
              <td @click.stop>
                <button
                  v-if="r.status === 'released' || r.status === 'completed'"
                  class="small"
                  :disabled="busyId === r.id"
                  @click="toggleReason(r.id)"
                >重开</button>
                <button
                  v-else-if="r.status === 'reopened'"
                  class="small"
                  :disabled="busyId === r.id"
                  @click="reinspect(r.id)"
                >再入检</button>
                <span v-else class="muted">—</span>
              </td>
            </tr>
            <tr v-if="showReasonBox === r.id" @click.stop>
              <td colspan="10">
                <div class="row" style="gap:8px; align-items:center">
                  <input
                    v-model="reopenReason"
                    placeholder="重开原因（必填），如：现场反馈数据错误，打回修复后重检"
                    style="flex:1"
                    @keyup.enter="reopen(r.id)"
                  />
                  <button class="small" :disabled="busyId === r.id" @click="reopen(r.id)">
                    {{ busyId === r.id ? '撤回中…' : '确认重开并撤回' }}
                  </button>
                  <button class="small" @click="toggleReason(r.id)">取消</button>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <div class="panel" v-if="detail">
      <h3>
        批次 #{{ detail.id }} 明细
        <span class="tag" :class="statusClass(detail.status)">{{ detail.status }}</span>
        <span class="tag">R{{ detail.round_no }}</span>
      </h3>

      <div v-if="detail.reopen_events && detail.reopen_events.length" class="panel" style="margin:12px 0">
        <h4>重开 / 撤回审计</h4>
        <table>
          <thead>
            <tr><th>时间</th><th>轮次</th><th>重开原因</th><th>精选区撤回</th><th>隔离区失效</th><th>再入检新批次</th></tr>
          </thead>
          <tbody>
            <tr v-for="e in detail.reopen_events" :key="e.id">
              <td>{{ e.created_at }}</td>
              <td>R{{ e.round_no }}</td>
              <td>{{ e.reason }}</td>
              <td><span class="tag warn">{{ e.curated_withdrawn_count }} 行</span></td>
              <td><span class="tag warn">{{ e.quarantine_superseded_count }} 行</span></td>
              <td>
                <a v-if="e.new_batch_id" href="#" @click.prevent="show(e.new_batch_id)">#{{ e.new_batch_id }}</a>
                <span v-else class="muted">待再入检</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="tiles" v-if="detail.reopen_reason">
        <div class="tile">
          <div class="hero-num">{{ detail.reopen_events?.[0]?.curated_withdrawn_count ?? 0 }}</div>
          <div class="muted">重开撤回条数</div>
        </div>
        <div class="tile">
          <div class="hero-num">{{ detail.curated_total ?? '—' }}</div>
          <div class="muted">当前数据集精选区存量</div>
        </div>
      </div>

      <p v-if="detail.reopen_reason" class="muted">重开原因：{{ detail.reopen_reason }}（{{ detail.reopened_at }}）</p>

      <div style="margin:12px 0" v-if="detail.status === 'released' || detail.status === 'completed'">
        <button class="small" :disabled="busyId === detail.id" @click="toggleReason(detail.id)">重开本批次</button>
      </div>
      <div style="margin:12px 0" v-else-if="detail.status === 'reopened'">
        <button class="small" :disabled="busyId === detail.id" @click="reinspect(detail.id)">
          {{ busyId === detail.id ? '再入检中…' : '修复完成，再入检（生成新一轮批次）' }}
        </button>
      </div>

      <h4>报告</h4>
      <pre class="muted" style="white-space:pre-wrap">{{ JSON.stringify(detail.report, null, 2) }}</pre>
    </div>
  </div>
</template>
