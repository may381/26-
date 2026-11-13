export type Risk = "low" | "medium" | "high";
export type Page =
  | "dashboard"
  | "assistant"
  | "alerts"
  | "reports"
  | "settings"
  | "knowledge"
  | "evaluation";
export interface Guardian {
  id: string;
  name: string;
  relation: string;
  phone: string;
  email?: string;
  isDefault: boolean;
}
export interface Settings {
  name: string;
  role: string;
  age: string;
  job: string;
  gender: string;
  preference: number;
  largeFont: boolean;
  guardians: Guardian[];
}
export interface Alert {
  origin?: 'backend';
  assessment?: 'assessed' | 'needs_review';
  sources?: {id:string; title:string; source:string; content:string}[];
  evidenceItems?: {id:string; excerpt:string; start:number; end:number}[];
  model?: string;
  profile?: Pick<Settings, 'role'|'age'|'job'|'preference'>;
  disposition?: 'viewed'|'safe'|'help';
  id: string;
  level: Risk;
  type: string;
  summary: string;
  time: string;
  user: string;
  handled: boolean;
  confidence: number | null;
  advice: string[];
  evidence: string;
  logs: string[];
  modality: string;
  transcript?: string;
  audioSegments?: {id:string; excerpt:string; start:number; end:number}[];
  audioDuration?: number;
  detectedLanguage?: string;
  voiceAuthenticity?: 'not_assessed' | 'experimental';
  imageObservedText?: string[];
  videoFrameTimes?: number[];
  videoOriginalStored?: boolean;
  fusionStrategy?: string;
}
export interface Report {
  id: string;
  start: string;
  end: string;
  type: string;
  created: string;
  user?: string;
  events?: Alert[];
  summary?: {total:number;handled:number;levels:Record<string,number>;types:Record<string,number>};
  data_source?: string;
}
export interface Knowledge {
  id: string;
  type: string;
  keywords: string;
  count: number;
  updated: string;
}
export interface Scenario {
  id: string;
  name: string;
  level: Risk;
  type: string;
  confidence: number;
  text: string;
  reply: string;
  advice: string[];
  modality: string;
}
