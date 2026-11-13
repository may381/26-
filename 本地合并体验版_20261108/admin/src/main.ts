import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Spots from './views/Spots.vue'
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/spots' },
    { path: '/spots', component: Spots },
  ],
})
createApp(App).use(router).mount('#app')
