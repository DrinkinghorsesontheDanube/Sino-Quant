<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NButton, NCard, NGrid, NGridItem, NTag } from 'naive-ui'

const router = useRouter()
</script>

<template>
  <div>
    <h1 class="page-title">板块总览</h1>
    <n-grid x-gap="16" y-gap="16" cols="1 s:2 l:3" responsive="screen">
      <n-grid-item>
        <n-card title="A 股量化" hoverable>
          <template #header-extra><n-tag size="small" type="success">已上线</n-tag></template>
          日线动量策略研究与回测：净值曲线、年化收益、最大回撤、夏普率、换手率与成交明细。
          <template #footer>
            <n-button type="primary" secondary @click="router.push('/a-share')">进入板块</n-button>
          </template>
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card title="港股量化" hoverable>
          <template #header-extra><n-tag size="small" type="warning">建设中</n-tag></template>
          预留：接入港股日线数据、约束模型（碎股交易、印花税）后按同一规范上线。
          <template #footer>
            <n-button disabled secondary>敬请期待</n-button>
          </template>
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card title="期货 / 期权" hoverable>
          <template #header-extra><n-tag size="small" type="warning">建设中</n-tag></template>
          预留：保证金模型、展期规则与希腊字母监控，复用统一门户壳。
          <template #footer>
            <n-button disabled secondary>敬请期待</n-button>
          </template>
        </n-card>
      </n-grid-item>
    </n-grid>
  </div>
</template>
