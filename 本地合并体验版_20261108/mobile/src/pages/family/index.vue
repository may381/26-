<script setup lang="ts">
function goBack() {
  uni.navigateBack()
}
</script>
<template>
  <view class="page"
    ><view class="title">家属服务</view
    ><text>家属绑定、授权和旅途关怀正在开发，当前尚不能接收求助通知。</text
    ><button @click="goBack">返回景点介绍</button></view
  >
</template>
<style scoped>
.page {
  padding: 40rpx;
  font-size: 36rpx;
  line-height: 1.8;
  color: #193e31;
}
.title {
  font-size: 48rpx;
  font-weight: 700;
  margin-bottom: 24rpx;
}
button {
  margin-top: 40rpx;
  font-size: 36rpx;
}
</style>
