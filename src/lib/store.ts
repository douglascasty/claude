import { getAuthedClient } from "./supabase.js";
import { newId } from "./local.js";
import type { HealthRecord } from "./health.js";

export interface Project {
  id: string;
  name: string;
  createdAt: string;
}

export interface ApiKey {
  id: string;
  name: string;
  projectId: string;
  token: string;
  createdAt: string;
  revokedAt: string | null;
}

interface ProjectRow {
  id: string;
  name: string;
  created_at: string;
}

interface ApiKeyRow {
  id: string;
  name: string;
  project_id: string;
  token: string;
  created_at: string;
  revoked_at: string | null;
}

export function mapProject(row: ProjectRow): Project {
  return { id: row.id, name: row.name, createdAt: row.created_at };
}

export function mapApiKey(row: ApiKeyRow): ApiKey {
  return {
    id: row.id,
    name: row.name,
    projectId: row.project_id,
    token: row.token,
    createdAt: row.created_at,
    revokedAt: row.revoked_at,
  };
}

export async function listProjects(): Promise<Project[]> {
  const { client } = await getAuthedClient();
  const { data, error } = await client
    .from("projects")
    .select("*")
    .order("created_at", { ascending: true });
  if (error) throw new Error(error.message);
  return (data as ProjectRow[]).map(mapProject);
}

export async function createProject(name: string): Promise<Project> {
  const { client, userId } = await getAuthedClient();
  const row = { id: newId("proj"), user_id: userId, name, created_at: new Date().toISOString() };
  const { data, error } = await client.from("projects").insert(row).select().single();
  if (error) throw new Error(error.message);
  return mapProject(data as ProjectRow);
}

export async function getProject(id: string): Promise<Project | null> {
  const { client } = await getAuthedClient();
  const { data, error } = await client.from("projects").select("*").eq("id", id).maybeSingle();
  if (error) throw new Error(error.message);
  return data ? mapProject(data as ProjectRow) : null;
}

export async function deleteProject(id: string): Promise<boolean> {
  const { client } = await getAuthedClient();
  const { data, error } = await client.from("projects").delete().eq("id", id).select();
  if (error) throw new Error(error.message);
  return (data as ProjectRow[]).length > 0;
}

export async function listApiKeys(projectId: string): Promise<ApiKey[]> {
  const { client } = await getAuthedClient();
  const { data, error } = await client
    .from("api_keys")
    .select("*")
    .eq("project_id", projectId)
    .order("created_at", { ascending: true });
  if (error) throw new Error(error.message);
  return (data as ApiKeyRow[]).map(mapApiKey);
}

export async function getApiKey(id: string): Promise<ApiKey | null> {
  const { client } = await getAuthedClient();
  const { data, error } = await client.from("api_keys").select("*").eq("id", id).maybeSingle();
  if (error) throw new Error(error.message);
  return data ? mapApiKey(data as ApiKeyRow) : null;
}

export async function createApiKey(projectId: string, name: string, token: string): Promise<ApiKey> {
  const { client, userId } = await getAuthedClient();
  const row = {
    id: newId("key"),
    user_id: userId,
    project_id: projectId,
    name,
    token,
    created_at: new Date().toISOString(),
    revoked_at: null,
  };
  const { data, error } = await client.from("api_keys").insert(row).select().single();
  if (error) throw new Error(error.message);
  return mapApiKey(data as ApiKeyRow);
}

export async function revokeApiKey(id: string): Promise<ApiKey | null> {
  const { client } = await getAuthedClient();
  const { data, error } = await client
    .from("api_keys")
    .update({ revoked_at: new Date().toISOString() })
    .eq("id", id)
    .select()
    .maybeSingle();
  if (error) throw new Error(error.message);
  return data ? mapApiKey(data as ApiKeyRow) : null;
}

export interface HealthRecordEntry {
  type: string;
  sourceName: string | null;
  unit: string | null;
  value: string;
  startDate: string;
}

interface HealthRecordRow {
  type: string;
  source_name: string | null;
  unit: string | null;
  value: string;
  start_date: string;
}

export interface HealthTypeSummary {
  type: string;
  count: number;
  firstDate: string;
  lastDate: string;
}

interface HealthSummaryRow {
  type: string;
  count: number;
  first_date: string;
  last_date: string;
}

function mapHealthRow(row: HealthRecordRow): HealthRecordEntry {
  return {
    type: row.type,
    sourceName: row.source_name,
    unit: row.unit,
    value: row.value,
    startDate: row.start_date,
  };
}

export async function insertHealthRecords(records: HealthRecord[]): Promise<number> {
  const { client, userId } = await getAuthedClient();
  const rows = records.map((r) => ({
    user_id: userId,
    type: r.type,
    source_name: r.sourceName,
    unit: r.unit,
    value: r.value,
    start_date: r.startDate,
    end_date: r.endDate,
  }));
  const { error, count } = await client.from("health_records").insert(rows, { count: "exact" });
  if (error) throw new Error(error.message);
  return count ?? rows.length;
}

export async function healthSummary(): Promise<HealthTypeSummary[]> {
  const { client } = await getAuthedClient();
  const { data, error } = await client.rpc("health_summary");
  if (error) throw new Error(error.message);
  return (data as HealthSummaryRow[]).map((row) => ({
    type: row.type,
    count: row.count,
    firstDate: row.first_date,
    lastDate: row.last_date,
  }));
}

export async function listHealthRecords(opts: {
  type?: string;
  since?: string;
  limit?: number;
}): Promise<HealthRecordEntry[]> {
  const { client } = await getAuthedClient();
  let query = client
    .from("health_records")
    .select("type, source_name, unit, value, start_date")
    .order("start_date", { ascending: false })
    .limit(opts.limit ?? 50);
  if (opts.type) {
    query = query.eq("type", opts.type);
  }
  if (opts.since) {
    query = query.gte("start_date", opts.since);
  }
  const { data, error } = await query;
  if (error) throw new Error(error.message);
  return (data as HealthRecordRow[]).map(mapHealthRow);
}
