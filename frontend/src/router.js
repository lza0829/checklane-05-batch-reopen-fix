import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './pages/Dashboard.vue'
import Datasets from './pages/Datasets.vue'
import Rules from './pages/Rules.vue'
import Inspect from './pages/Inspect.vue'
import Batches from './pages/Batches.vue'
import Quarantine from './pages/Quarantine.vue'
import Curated from './pages/Curated.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/datasets', component: Datasets },
    { path: '/rules', component: Rules },
    { path: '/inspect', component: Inspect },
    { path: '/batches', component: Batches },
    { path: '/quarantine', component: Quarantine },
    { path: '/curated', component: Curated },
  ],
})
