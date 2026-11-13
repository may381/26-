<script>
// Geometry is shared across cards; progress always comes from the current tour.
const routeMaps = new Map()
const pendingMaps = new Map()
</script>

<script setup>
import { computed, ref, watch } from 'vue'
import { getRouteMap } from '../api/index.js'

const props = defineProps({ tour: { type: Object, required: true }, adjusted: Boolean })
const map = ref(null)
const loading = ref(false)
let requestVersion = 0
const routeId = computed(() => props.tour?.backend && props.tour?.routeId || null)
const valid = p => p && Number.isFinite(p.lat) && Number.isFinite(p.lng)
watch(routeId, async id => {
  const version = ++requestVersion
  map.value = null
  loading.value = false
  if (!id) return
  if (routeMaps.has(id)) { map.value = routeMaps.get(id); return }
  loading.value = true
  try {
    if (!pendingMaps.has(id)) {
      pendingMaps.set(id, getRouteMap(id).then(response => {
        const data = response
        if (!Array.isArray(data?.spots) || !data.spots.length ||
          !data.spots.every(s => valid(s.location)) || !Array.isArray(data.legs)) throw new Error('Invalid geometry')
        routeMaps.set(id, data)
        return data
      }).finally(() => pendingMaps.delete(id)))
    }
    const data = await pendingMaps.get(id)
    if (version === requestVersion) map.value = data
  } catch { /* Static illustration is also available offline. */ }
  finally { if (version === requestVersion) loading.value = false }
}, { immediate: true })

const isMock = computed(() => map.value?.source === 'MOCK')
const xml = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c]))
const clamp = (v, min, max) => Math.max(min, Math.min(max, v))
// Bounded controls keep the smoothed curve inside its projected bounds.
function smooth(points) {
  if (!points.length) return ''
  let d = `M ${points[0].x} ${points[0].y}`
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[Math.max(0, i - 1)], b = points[i], c = points[i + 1], e = points[Math.min(points.length - 1, i + 2)]
    const bound = (v, key) => clamp(v, Math.min(b[key], c[key]), Math.max(b[key], c[key]))
    d += ` C ${bound(b.x + (c.x - a.x) / 6, 'x')} ${bound(b.y + (c.y - a.y) / 6, 'y')} ${bound(c.x - (e.x - b.x) / 6, 'x')} ${bound(c.y - (e.y - b.y) / 6, 'y')} ${c.x} ${c.y}`
  }
  return d
}
const svgUrl = computed(() => {
  if (!map.value) return ''
  const data = map.value
  const all = [...data.spots.map(s => s.location), ...data.legs.flatMap(l => (l.path || []).filter(valid))]
  const lngs = all.map(p => p.lng), lats = all.map(p => p.lat)
  const minX = Math.min(...lngs), maxX = Math.max(...lngs), minY = Math.min(...lats), maxY = Math.max(...lats)
  const dx = Math.max(maxX - minX, .0001), dy = Math.max(maxY - minY, .0001)
  const scale = Math.min(550 / dx, 280 / dy)
  const project = p => ({ x: 345 + (p.lng - (minX + maxX) / 2) * scale, y: 210 - (p.lat - (minY + maxY) / 2) * scale })
  const spots = data.spots.map(s => ({ ...s, ...project(s.location) }))
  const visited = new Set((props.tour?.visitedSpotIds || []).map(String))
  const skipped = new Set((props.tour?.skippedSpotIds || []).map(String))
  const legs = data.legs.map(l => {
    const points = (l.path || []).filter(valid).map(project)
    if (points.length < 2) {
      const from = spots.find(s => String(s.id) === String(l.fromSpotId)), to = spots.find(s => String(s.id) === String(l.toSpotId))
      if (from && to) points.splice(0, points.length, from, to)
    }
    const skip = skipped.has(String(l.toSpotId))
    return { points, skip, color: skip ? '#B9B0A0' : visited.has(String(l.fromSpotId)) ? '#2E9E6B' : '#006AFF' }
  })
  const path = (l, white) => `<path d="${smooth(l.points)}" fill="none" stroke="${white ? '#fff' : l.color}" stroke-width="${white ? 12 : l.skip ? 5 : 6}" stroke-linecap="round" stroke-linejoin="round" ${!white && l.skip ? 'stroke-dasharray="8 9"' : ''}/>`
  const labels = []
  const overlap = (a, b) => a.x < b.x + b.w + 5 && a.x + a.w + 5 > b.x && a.y < b.y + b.h + 5 && a.y + a.h + 5 > b.y
  const linePoints = legs.flatMap(l => l.points.slice(1).flatMap((p, i) => {
    const a = l.points[i], n = Math.max(1, Math.ceil(Math.hypot(p.x - a.x, p.y - a.y) / 8))
    return Array.from({ length: n + 1 }, (_, j) => ({ x: a.x + (p.x - a.x) * j / n, y: a.y + (p.y - a.y) * j / n }))
  }))
  const labelSvg = spots.map((s, i) => {
    const text = `${i === 0 ? '起点 · ' : i === spots.length - 1 ? '终点 · ' : ''}${s.name}`
    const w = Math.min(620, Array.from(text).reduce((n, c) => n + (c.charCodeAt(0) > 255 ? 21 : 12), 0) + 12)
    const candidates = []
    for (const offset of [0, 32, 64, 96, 128, 160]) for (const side of (i % 2 ? [1, -1] : [-1, 1])) for (const shift of [0, -w / 2, w / 2]) {
      const box = { x: clamp(s.x - w / 2 + shift, 12, 678 - w), y: clamp(s.y + (side < 0 ? -48 - offset : 23 + offset), 14, 352), w, h: 28 }
      const score = labels.filter(b => overlap(box, b)).length * 10000 + spots.filter(p => overlap(box, { x: p.x - 15, y: p.y - 15, w: 30, h: 30 })).length * 10000 + linePoints.filter(p => overlap(box, { ...p, w: 1, h: 1 })).length * 100 + offset + Math.abs(shift) / 4 + (overlap(box, { x: 613, y: 12, w: 65, h: 76 }) ? 10000 : 0)
      candidates.push({ ...box, score })
    }
    candidates.sort((a, b) => a.score - b.score)
    const box = candidates[0]; labels.push(box)
    return `<text x="${box.x + box.w / 2}" y="${box.y + 21}" text-anchor="middle" textLength="${box.w - 12}" lengthAdjust="spacingAndGlyphs" font-size="21" fill="#17324D" stroke="#F7F2E8" stroke-width="5" paint-order="stroke">${xml(text)}</text>`
  }).join('')
  const bounds = { x: Math.min(...spots.map(s => s.x), ...linePoints.map(p => p.x)) - 22, y: Math.min(...spots.map(s => s.y), ...linePoints.map(p => p.y)) - 22 }
  bounds.w = Math.max(...all.map(p => project(p).x)) + 22 - bounds.x
  bounds.h = Math.max(...all.map(p => project(p).y)) + 22 - bounds.y
  const decorations = [{ x: 24, y: 10, w: 112, h: 28 }, { x: 475, y: 10, w: 108, h: 28 }, { x: 525, y: 370, w: 130, h: 30 }, { x: 25, y: 310, w: 90, h: 55 }, { x: 220, y: 10, w: 100, h: 28 }].filter(b => !overlap(b, bounds) && !labels.some(l => overlap(b, l))).slice(0, 3)
  const decor = decorations.map((b, i) => `<ellipse cx="${b.x + b.w / 2}" cy="${b.y + b.h / 2}" rx="${b.w / 2}" ry="${b.h / 2}" fill="${i === 1 ? '#DCEAF5' : '#E4EDD8'}" ${i === 1 ? 'stroke="#C9DDF0"' : ''}/><path d="M ${b.x + 15} ${b.y + 16} v 18" stroke="#BFD3A8" stroke-width="3"/><circle cx="${b.x + 15}" cy="${b.y + 14}" r="9" fill="#BFD3A8"/>`).join('')
  const markers = spots.map(s => {
    const skip = skipped.has(String(s.id)), current = !skip && String(props.tour?.currentSpotId) === String(s.id), done = visited.has(String(s.id))
    return `${current ? `<circle cx="${s.x}" cy="${s.y}" r="20" fill="none" stroke="#006AFF" stroke-width="5" opacity=".22"/>` : ''}<circle cx="${s.x}" cy="${s.y}" r="${skip ? 8 : current ? 11 : 9}" fill="${skip ? '#EFE9DE' : current ? '#006AFF' : done ? '#2E9E6B' : '#fff'}" stroke="${skip ? '#B9B0A0' : current || done ? '#fff' : '#006AFF'}" stroke-width="${current ? 4 : 3}"/>${skip ? `<path d="M ${s.x - 5} ${s.y + 5} l 10 -10" stroke="#B9B0A0" stroke-width="2"/>` : ''}`
  }).join('')
  const facilities = (data.facilities || []).filter(f => ['TOILET', 'MEDICAL'].includes(f.type) && valid(f.location)).map(f => project(f.location)).filter(p => p.x >= 20 && p.x <= 670 && p.y >= 20 && p.y <= 370 && !labels.some(b => overlap(b, { ...p, w: 5, h: 5 }))).map(p => `<circle cx="${p.x}" cy="${p.y}" r="4" fill="#7FA8C9"/>`).join('')
  const arrows = legs.filter(l => l.points.length > 1).slice(0, 3).map(l => {
    const i = Math.floor((l.points.length - 1) / 2), a = l.points[i], b = l.points[i + 1]
    return `<path d="M -6 -5 L 6 0 L -6 5 Z" fill="${l.color}" transform="translate(${(a.x + b.x) / 2} ${(a.y + b.y) / 2}) rotate(${Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI})"/>`
  }).join('')
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="690" height="420" viewBox="0 0 690 420" font-family="system-ui, sans-serif"><defs><pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="13" cy="13" r="1.3" fill="#E6DCC8"/></pattern></defs><rect width="690" height="420" rx="28" fill="#F7F2E8"/><rect width="690" height="420" rx="28" fill="url(#dots)"/>${decor}${legs.map(l => path(l, true)).join('')}${legs.map(l => path(l, false)).join('')}${arrows}${facilities}${markers}${labelSvg}<g opacity=".55" fill="#17324D" stroke="#17324D"><circle cx="645" cy="53" r="22" fill="none"/><path d="M 645 37 L 638 63 L 645 57 L 652 63 Z"/><text x="645" y="22" text-anchor="middle" stroke="none" font-size="16">N</text></g><text x="24" y="399" fill="#8A7F6C" font-size="16">演示点位 · 非真实导航</text></svg>`
  return `url("data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}")`
})
</script>

<template>
  <view class="rm-card">
    <view class="rm-head"><text class="rm-title">路线图</text><text v-if="isMock" class="rm-badge">演示点位</text></view>
    <view v-if="loading || map" class="rm-canvas" :style="{ backgroundImage: svgUrl }" role="img" aria-label="游览路线示意图，非真实导航">
      <text v-if="loading" class="rm-loading" role="status">正在绘制路线…</text>
    </view>
    <image v-else class="rm-fallback" src="/static/outing/ongoing.jpg" mode="widthFix" />
    <view v-if="map" class="rm-legend"><text class="rm-dot rm-dot-blue"></text><text>未到</text><text class="rm-dot rm-dot-green"></text><text>已到</text><text class="rm-dash"></text><text>已跳过</text></view>
    <text class="rm-note">{{ map || loading ? '路线为高德计算的演示几何，仅供演示，不能作为真实导航。' : '路线暂时无法绘制' }}</text>
  </view>
</template>

<style scoped>
.rm-card{box-sizing:border-box;width:100%;min-width:0;max-width:100%;padding:calc(var(--u)*20);background:#fff;border-radius:calc(var(--u)*28)}
.rm-head{display:flex;align-items:center;justify-content:space-between;gap:calc(var(--u)*12);margin-bottom:calc(var(--u)*16)}
.rm-title{font-size:calc(var(--u)*34);font-weight:750;color:#071537}
.rm-badge{flex-shrink:0;padding:calc(var(--u)*5) calc(var(--u)*14);border-radius:999px;background:#EEF4FF;color:#006AFF;font-size:calc(var(--u)*22)}
.rm-canvas{position:relative;width:100%;aspect-ratio:690/420;background-color:#F7F2E8;background-size:100% 100%;background-repeat:no-repeat;box-sizing:border-box;border:1px solid #EDE5D6;border-radius:calc(var(--u)*20);overflow:hidden}
.rm-loading{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:calc(var(--u)*26);color:#8A7F6C}
.rm-fallback{display:block;width:100%;height:auto;border-radius:calc(var(--u)*20)}
.rm-legend{display:flex;align-items:center;flex-wrap:wrap;gap:calc(var(--u)*12);margin-top:calc(var(--u)*16);font-size:calc(var(--u)*22);color:#17324D}
.rm-dot{width:calc(var(--u)*14);height:calc(var(--u)*14);border-radius:50%;flex-shrink:0}.rm-dot-blue{background:#006AFF}.rm-dot-green{background:#2E9E6B}
.rm-dash{width:calc(var(--u)*28);height:0;border-top:2px dashed #B9B0A0;margin-left:calc(var(--u)*8)}
.rm-note{display:block;margin-top:calc(var(--u)*12);font-size:calc(var(--u)*22);color:#8A7F6C;line-height:1.5;overflow-wrap:anywhere}
</style>
