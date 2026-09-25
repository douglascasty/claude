import { getAuthedClient } from "./supabase.js";
import { newId } from "./local.js";

export interface Project {
  id: string;
  name: string;
  createdAt: string;
}

interface ProjectRow {
  id: string;
  name: string;
  created_at: string;
}

export function mapProject(row: ProjectRow): Project {
  return { id: row.id, name: row.name, createdAt: row.created_at };
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
