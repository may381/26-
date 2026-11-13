import { Alert, Report, Settings } from "../types";
const profile = (settings: Settings) => ({role:settings.role,age:settings.age,job:settings.job,preference:settings.preference});
export class ApiError extends Error {
  constructor(message: string, public readonly status: number) { super(message); this.name = 'ApiError'; }
}
async function request<T>(path: string, init?: RequestInit, timeout = 10000): Promise<T> {
  let r: Response;
  const multipart = init?.body instanceof FormData;
  try { r = await fetch("/api" + path, { ...init, headers: { ...(multipart ? {} : {"Content-Type": "application/json"}), ...init?.headers }, signal: AbortSignal.timeout(timeout) }); }
  catch (error) {
    if (error instanceof DOMException && (error.name === "TimeoutError" || error.name === "AbortError")) {
      throw new Error("请求等待超时，处理结果尚未确认。请刷新记录核对，避免重复发送通知。");
    }
    throw new Error("无法连接后端，请运行 start-school-backend.bat，并确认前端已重启");
  }
  if (!r.ok) { const body = await r.json().catch(() => null); throw new ApiError(typeof body?.detail === "string" ? body.detail : "请求失败，请检查输入或稍后重试", r.status); }
  return r.json();
}
export const api = {
  health: () => request<{model_configured: boolean; model_ready: boolean; provider: string; model: string; case_count: number;database_ready:boolean;alert_count:number;knowledge_count:number;speech_model:string;speech_cache_dir:string;speech_loaded:boolean;embedding_model:string;embedding_ready:boolean;knowledge_chunk_count:number;retrieval:string}>("/health"),
  alerts: () => request<Alert[]>("/alerts"),
  memory: (username:string) => request<{username:string;count:number;items:Alert[]}>("/memory/"+encodeURIComponent(username)),
  deleteMemory: (username:string) => request<{ok:boolean;deleted:number}>("/memory/"+encodeURIComponent(username),{method:'DELETE'}),
  backup: () => request<Record<string,unknown>>("/backup"),
  reports: () => request<Report[]>("/reports"),
  createReport: (start:string,end:string,type:string,user:string) => request<Report>("/reports",{method:"POST",body:JSON.stringify({start,end,type,user})}),
  handle: (ids: string[]) => request("/alerts/handle", {method:"POST", body:JSON.stringify({ids})}),
  notify: (id: string, guardians: string[]) => request<Alert>("/alerts/" + encodeURIComponent(id) + "/notify", {method:"POST", body:JSON.stringify({guardians})}),
  emailNotify: (id:string, recipients:string[]) => request<Alert>("/alerts/"+encodeURIComponent(id)+"/email", {method:'POST',body:JSON.stringify({recipients})}, 25000),
  disposition: (id:string, action:'viewed'|'safe'|'help') => request<Alert>("/alerts/"+encodeURIComponent(id)+"/disposition",{method:'POST',body:JSON.stringify({action})}),
  knowledge: () => request<KnowledgeStats>('/knowledge'),
  ingestKnowledge: (fraud_type: string, content: string, source_name: string) => request<{id:string;created:string;characters:number;cleaned:boolean}>('/knowledge', {method:'POST',body:JSON.stringify({fraud_type,content,source_name})}, 30000),
  knowledgeCases: (query='') => request<KnowledgeCase[]>('/knowledge/cases?query='+encodeURIComponent(query)),
  updateKnowledge: (id:string,fraud_type:string,content:string) => request('/knowledge/cases/'+encodeURIComponent(id),{method:'PUT',body:JSON.stringify({fraud_type,content})}),
  deleteKnowledge: (id:string) => request('/knowledge/cases/'+encodeURIComponent(id),{method:'DELETE'}),
  reviewKnowledge: (id:string,status:'approved'|'disabled') => request('/knowledge/cases/'+encodeURIComponent(id)+'/review',{method:'POST',body:JSON.stringify({status})},300000),
  knowledgeVersions: () => request<KnowledgeVersion[]>('/knowledge/versions'),
  createKnowledgeVersion: (name:string) => request<KnowledgeVersion>('/knowledge/versions',{method:'POST',body:JSON.stringify({name})}),
  publishKnowledgeVersion: (id:string) => request('/knowledge/versions/'+encodeURIComponent(id)+'/publish',{method:'POST'}),
  restoreKnowledgeVersion: (id:string) => request('/knowledge/versions/'+encodeURIComponent(id)+'/restore',{method:'POST'},300000),
  retrieveKnowledge: (text:string) => request<{items:KnowledgeMatch[];method:string}>('/knowledge/retrieve',{method:'POST',body:JSON.stringify({text})}),
  reindexKnowledge: () => request<{ok:boolean;chunks:number;documents:number;model:string}>('/knowledge/reindex',{method:'POST'},300000),
  submit: (text: string, settings: Settings, key: string) => request<{analysis_id:string}>("/analyses", {method:"POST",headers:{"Idempotency-Key":key},body:JSON.stringify({text,username:settings.name,profile:profile(settings)})}),
  analyzeImage: (image_data_url: string, note: string, settings: Settings) => request<Alert>("/image-analyses", {method:"POST",body:JSON.stringify({image_data_url,note,username:settings.name,profile:profile(settings)})}, 150000),
  analyzeAudio: (file: File, note: string, settings: Settings) => {
    const form = new FormData();
    form.append("file", file); form.append("note", note); form.append("username", settings.name);
    form.append("profile", JSON.stringify(profile(settings)));
    return request<Alert>("/audio-analyses", {method:"POST",body:form}, 360000);
  },
  analyzeVideo: (file: File, note: string, settings: Settings) => {
    const form = new FormData();
    form.append("file", file); form.append("note", note); form.append("username", settings.name);
    form.append("profile", JSON.stringify(profile(settings)));
    return request<Alert>("/video-analyses", {method:"POST",body:form}, 600000);
  },
  analyzeMultimodal: (text: string, image: File|null, audio: File|null, settings: Settings) => {
    const form = new FormData();
    form.append("text_input", text); form.append("username", settings.name);
    form.append("profile", JSON.stringify(profile(settings)));
    if(image) form.append("image", image); if(audio) form.append("audio", audio);
    return request<Alert>("/multimodal-analyses", {method:"POST",body:form}, 480000);
  },
  task: (id: string) => request<{status:string; error:string|null; result:Alert|null}>("/analyses/" + encodeURIComponent(id)),
  evaluationCases: () => request<EvaluationCase[]>("/evaluation-cases"),
  startEvaluation: (mode: 'rules'|'model', settings: Settings, dataset_split='all', ablation='full') => request<{evaluation_id:string}>("/evaluations", {method:'POST',body:JSON.stringify({mode,profile:profile(settings),dataset_split,ablation})}),
  evaluation: (id: string) => request<EvaluationRun>("/evaluations/" + encodeURIComponent(id), undefined, 15000),
};
export type EvaluationCase = {id:string;label:'fraud'|'normal';type:string;modality:'text'|'image'|'audio';text:string;asset?:string;asset_url?:string;split?:'development'|'validation'|'blind'};
export type EvaluationMetrics = {total:number;completed:number;failed:number;tp:number;tn:number;fp:number;fn:number;accuracy:number;precision:number;recall:number;f1:number;false_positive_rate:number;type_accuracy:number;average_latency_ms:number};
export type EvaluationItem = EvaluationCase & {prediction:'fraud'|'normal'|'error';predicted_type:string;correct:boolean;latency_ms:number;evaluation_scope?:string;transcript?:string|null;error?:string|null};
export type EvaluationResult = {mode:'rules'|'model';model:string;dataset_split?:string;ablation?:string;dataset:{total:number;fraud:number;normal:number;fraud_types:number};metrics:EvaluationMetrics;modality_metrics:Record<'text'|'image'|'audio',EvaluationMetrics>;items:EvaluationItem[]};
export type EvaluationRun = {evaluation_id:string;mode:'rules'|'model';status:string;progress:number;error:string|null;result:EvaluationResult|null;created:string};
export type KnowledgeCase = {id:string;fraud_type:string;content:string;source_name:string;created:string;review_status:'approved'|'disabled'};
export type KnowledgeVersion = {id:string;name:string;status:'draft'|'active'|'archived';created:string;published?:string|null;case_count:number};
export type KnowledgeStats = {official_count:number;user_count:number;groups:{fraud_type:string;count:number;updated:string}[];embedding_model:string;embedding_ready:boolean;chunk_count:number;indexed_document_count:number;retrieval:string};
export type KnowledgeMatch = {id:string;title:string;source:string;content:string;score:number|null;semantic_score:number|null;keyword_score:number|null};
