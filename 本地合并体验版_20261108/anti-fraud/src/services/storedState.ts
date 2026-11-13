// Browser caches can outlive a release. Validate before React renders their fields.
const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === 'string';
const texts = (value: unknown) => Array.isArray(value) && value.every(text);
const date = (value: unknown) => text(value) && Number.isFinite(Date.parse(value));
const guardian = (value: unknown) => object(value)
  && ['id', 'name', 'relation', 'phone'].every(key => text(value[key]))
  && typeof value.isDefault === 'boolean' && (value.email === undefined || text(value.email));
const alert = (value: unknown): boolean => object(value)
  && ['id', 'type', 'summary', 'user', 'evidence', 'modality'].every(key => text(value[key]))
  && ['low', 'medium', 'high'].includes(String(value.level)) && date(value.time)
  && typeof value.handled === 'boolean' && texts(value.advice) && texts(value.logs)
  && (value.sources === undefined || Array.isArray(value.sources) && value.sources.every(source =>
    object(source) && ['id', 'title', 'source', 'content'].every(key => text(source[key]))))
  && (value.evidenceItems === undefined || Array.isArray(value.evidenceItems) && value.evidenceItems.every(item =>
    object(item) && text(item.id) && text(item.excerpt) && typeof item.start === 'number' && typeof item.end === 'number'));
const report = (value: unknown) => object(value)
  && ['id', 'type', 'start', 'end'].every(key => text(value[key])) && date(value.created)
  && (value.events === undefined || Array.isArray(value.events) && value.events.every(alert));
const knowledge = (value: unknown) => object(value)
  && ['id', 'type', 'keywords', 'updated'].every(key => text(value[key]))
  && typeof value.count === 'number' && Number.isFinite(value.count);

export function restoreStored<T>(key: string, raw: string | null, fallback: T): T {
  if (raw === null || raw.length > 8 * 1024 * 1024) return fallback;
  try {
    const value: unknown = JSON.parse(raw);
    if (key === 'anzhi-session') return (typeof value === 'boolean' ? value : fallback) as T;
    if (key === 'anzhi-settings') {
      if (!object(value) || !object(fallback)) return fallback;
      const restored: Record<string, unknown> = { ...fallback };
      for (const field of ['name', 'role', 'age', 'job', 'gender']) {
        if (text(value[field])) restored[field] = value[field];
      }
      if (typeof value.largeFont === 'boolean') restored.largeFont = value.largeFont;
      if (typeof value.preference === 'number' && Number.isFinite(value.preference)
          && value.preference >= 0 && value.preference <= 100) restored.preference = value.preference;
      if (Array.isArray(value.guardians)) restored.guardians = value.guardians.filter(guardian).slice(0, 100);
      return restored as T;
    }
    const validators: Record<string, (item: unknown) => boolean> = {
      'anzhi-alerts': alert, 'anzhi-reports': report, 'anzhi-knowledge': knowledge, 'anzhi-updates': text,
    };
    return (Array.isArray(value) && validators[key]
      ? value.slice(0, 10000).filter(validators[key]) : fallback) as T;
  } catch { return fallback; }
}
