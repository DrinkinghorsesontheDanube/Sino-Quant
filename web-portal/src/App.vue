<script setup lang="ts">
import { computed, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NConfigProvider, NLayout, NLayoutSider, NMenu, darkTheme, dateZh, zhCN, type MenuOption } from 'naive-ui'

const route = useRoute()
const router = useRouter()

const menuOptions: MenuOption[] = [
  { label: '总览', key: '/' },
  {
    label: 'A 股量化',
    key: '/a-share',
    children: [
      { label: '回测报告', key: '/a-share' },
    ],
  },
  {
    label: '港股量化（建设中）',
    key: 'h-share-hold',
    disabled: true,
  },
  {
    label: '期货期权（建设中）',
    key: 'futures-hold',
    disabled: true,
  },
]

const activeKey = computed(() => (route.path.startsWith('/a-share') ? '/a-share' : '/'))

function onMenuSelect(key: string) {
  if (key.startsWith('/')) void router.push(key)
}

const brand = h('div', { class: 'brand' }, [
  h('span', { class: 'brand-main' }, 'Quant Portal'),
  h('span', { class: 'brand-sub' }, '多板块量化门户'),
])
</script>

<template>
  <n-config-provider :theme="darkTheme" :locale="zhCN" :date-locale="dateZh" class="app-root">
    <n-layout has-sider position="absolute">
      <n-layout-sider bordered :width="230" collapse-mode="width" content-style="display:flex; flex-direction:column;">
        <component :is="brand" />
        <n-menu :options="menuOptions" :value="activeKey" @update:value="onMenuSelect" />
        <div class="sider-foot">V1 · 只读看结果</div>
      </n-layout-sider>
      <n-layout content-style="padding: 20px 28px; overflow-y: auto;">
        <router-view />
      </n-layout>
    </n-layout>
  </n-config-provider>
</template>

<style scoped>
.app-root :deep(.layout) { background: transparent; }
</style>
