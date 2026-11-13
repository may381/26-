/** Only explicit web source URLs may become clickable evidence links. */
export function safeSourceUrl(value: string | undefined): string | undefined {
  if (!value || value !== value.trim()) return undefined;
  try {
    const url = new URL(value);
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) return undefined;
    return url.href;
  } catch { return undefined; }
}
