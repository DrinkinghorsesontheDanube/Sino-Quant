import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: () => import('@/views/OverviewView.vue') },
    { path: '/a-share', name: 'a-share', component: () => import('@/views/a-share/ReportListView.vue') },
    {
      path: '/a-share/:runId',
      name: 'a-share-detail',
      component: () => import('@/views/a-share/ReportDetailView.vue'),
      props: true,
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

export default router
