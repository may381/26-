export interface Spot {
  id: string
  name: string
  description: string
}
interface ApiResponse<T> {
  code: string
  message: string
  data: T
}
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json' },
  })
  const body = (await response.json()) as ApiResponse<T>
  if (!response.ok || body.code !== 'OK') throw new Error(body.message || '请求失败')
  return body.data
}
export const listSpots = () => request<Spot[]>('/spots')
export const createSpot = (data: Pick<Spot, 'name' | 'description'>) =>
  request<Spot>('/spots', { method: 'POST', body: JSON.stringify(data) })
