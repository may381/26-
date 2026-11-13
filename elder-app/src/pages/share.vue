<template><ShareScreen :share-id="shareId"/></template>
<script setup>
import {ref} from 'vue'
import {onLoad} from '@dcloudio/uni-app'
import ShareScreen from '../components/ShareScreen.vue'
const shareId = ref('')
onLoad(query => {
  const q = query || {}
  shareId.value = q.shareId || q.id || ''
})
</script>
