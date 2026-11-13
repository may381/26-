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
let baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8080'
// #ifdef H5
baseUrl = import.meta.env.VITE_API_BASE_URL || ''
// #endif
export function listSpots(): Promise<Spot[]> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${baseUrl}/api/spots`,
      timeout: 10000,
      success(response) {
        const body = response.data as ApiResponse<Spot[]>
        if (response.statusCode === 200 && body.code === 'OK') resolve(body.data)
        else reject(new Error(body.message || '读取景点失败'))
      },
      fail() {
        reject(new Error('暂时无法连接，请稍后重试'))
      },
    })
  })
}
