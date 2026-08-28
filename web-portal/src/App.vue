<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NConfigProvider,
  NLayout,
  NLayoutSider,
  NMenu,
  NMessageProvider,
  darkTheme,
  type MenuOption,
} from 'naive-ui'

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
</script>

<template>
  <n-config-provider :theme="darkTheme">
    <!-- useMessage() 等反馈组件依赖这里的 Provider，缺失会导致页面组件挂载失败 -->
    <n-message-provider>
      <n-layout has-sider position="absolute">
        <n-layout-sider bordered :width="230" content-style="display:flex; flex-direction:column;">
          <div class="brand">
            <span class="brand-main">Quant Portal</span>
            <span class="brand-sub">多板块量化门户</span>
          </div>
          <n-menu :options="menuOptions" :value="activeKey" @update:value="onMenuSelect" />
          <div class="sider-foot">V1 · 只读看结果</div>
        </n-layout-sider>
        <n-layout content-style="padding: 20px 28px; overflow-y: auto;">
          <router-view />
        </n-layout>
      </n-layout>
    </n-message-provider>
  </n-config-provider>
</template>

<style>
.brand {
  padding: 18px 20px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.brand-main {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.4px;
}
.brand-sub {
  font-size: 12px;
  opacity: 0.55;
}
.sider-foot {
  margin-top: auto;
  padding: 14px 20px;
  font-size: 12px;
  opacity: 0.45;
}
</style>
