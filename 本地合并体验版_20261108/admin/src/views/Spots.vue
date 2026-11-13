<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { createSpot, listSpots, type Spot } from '../api/spots'
const spots = ref<Spot[]>([]),
  name = ref(''),
  description = ref('')
const saving = ref(false),
  loading = ref(false),
  error = ref(''),
  notice = ref('')
async function load() {
  loading.value = true
  error.value = ''
  try {
    spots.value = await listSpots()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '连接失败'
  } finally {
    loading.value = false
  }
}
async function save() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    const spot = await createSpot({
      name: name.value.trim(),
      description: description.value.trim(),
    })
    spots.value.unshift(spot)
    name.value = ''
    description.value = ''
    notice.value = '已保存。游客端刷新后可看到这条景点介绍。'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>
<template>
  <h1>景点介绍管理</h1>
  <p>添加游客在旅途中可以阅读的景点介绍。</p>
  <p>当前为本地开发演示，账号与权限功能待接入。</p>
  <form @submit.prevent="save">
    <label
      >景点名称<input
        v-model="name"
        required
        maxlength="100"
        placeholder="例如：示范园·湖畔步道" /></label
    ><label
      >景点介绍<textarea
        v-model="description"
        rows="4"
        maxlength="2000"
        placeholder="介绍景点特色"
      ></textarea></label
    ><button :disabled="saving || loading || !name.trim()">
      {{ saving ? '正在保存…' : '保存景点' }}
    </button>
  </form>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="notice" role="status">{{ notice }}</p>
  <h2>已录入景点</h2>
  <button :disabled="loading || saving" @click="load">刷新列表</button>
  <p v-if="loading" role="status">正在加载…</p>
  <p v-else-if="!spots.length && !error">暂无景点，请先添加。</p>
  <article v-for="spot in spots" :key="spot.id">
    <h3>{{ spot.name }}</h3>
    <p>{{ spot.description || '暂无介绍' }}</p>
  </article>
</template>
