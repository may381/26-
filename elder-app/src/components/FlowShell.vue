<script setup>
import {onShow} from '@dcloudio/uni-app'
import {state,refreshState,back} from './app-state.js'
defineProps({title:String,subtitle:String,kit:Boolean});onShow(refreshState)
</script><template><view class="flow" :class="[state.settings.fontSize,{'flow-kit':kit}]"><view class="flow-header"><button aria-label="返回" @click="back"><image src="/static/outing/icons/back.svg"/></button><view><text class="flow-title">{{title}}</text><text v-if="subtitle" class="flow-subtitle">{{subtitle}}</text></view></view><slot/><slot name="bottom"/></view></template>
