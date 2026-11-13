export function readBrowser(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
export function writeBrowser(key: string, value: string): boolean {
  try { localStorage.setItem(key, value); return true; } catch { return false; }
}
export function removeBrowser(key: string): boolean {
  try { localStorage.removeItem(key); return true; } catch { return false; }
}
