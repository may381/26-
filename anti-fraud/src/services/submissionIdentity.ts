export type SubmissionIdentity = { fingerprint: string; key: string };
export function restoreSubmission(raw: string | null): SubmissionIdentity | null {
  try {
    const value=JSON.parse(raw || 'null');
    return value && typeof value.fingerprint === 'string' && /^[a-f0-9]{64}$/.test(value.fingerprint)
      && typeof value.key === 'string' && /^[a-f0-9-]{36}$/.test(value.key)
      ? {fingerprint:value.fingerprint,key:value.key} : null;
  } catch { return null; }
}
export async function submissionFingerprint(fields: unknown[]): Promise<string> {
  const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(fields)));
  return Array.from(new Uint8Array(bytes),value=>value.toString(16).padStart(2,'0')).join('');
}
