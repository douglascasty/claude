import { getAuthedClient } from "./supabase.js";
import { newId } from "./local.js";

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
