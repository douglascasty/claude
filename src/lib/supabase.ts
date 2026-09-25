import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { loadState, saveState } from "./local.js";
import { fail } from "./output.js";

export function resolveSupabaseConfig(): { url: string; anonKey: string } {
  const state = loadState();
  const url = process.env.SUPABASE_URL ?? state.config.supabase_url;
  const anonKey = process.env.SUPABASE_ANON_KEY ?? state.config.supabase_anon_key;
  if (!url || !anonKey) {
    fail(
      "Supabase is not configured. Run `claude-console config set supabase_url <url>` " +
        "and `claude-console config set supabase_anon_key <key>`, or set SUPABASE_URL / " +
        "SUPABASE_ANON_KEY environment variables.",
    );
  }
  return { url, anonKey };
}

let cached: { client: SupabaseClient; key: string } | null = null;

export function getSupabaseClient(): SupabaseClient {
  const { url, anonKey } = resolveSupabaseConfig();
  const key = `${url}:${anonKey}`;
  if (cached?.key === key) {
    return cached.client;
  }
  const client = createClient(url, anonKey, {
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  });
  cached = { client, key };
  return client;
}

/**
 * Re-hydrates a Supabase session from the local cache for this CLI
 * invocation (each invocation is a fresh process, so there is nothing for
 * supabase-js's own session persistence to reattach to), and persists back
 * any refreshed token pair so the next invocation doesn't need to log in
 * again.
 */
export async function getAuthedClient(): Promise<{ client: SupabaseClient; userId: string }> {
  const client = getSupabaseClient();
  const state = loadState();
  if (!state.session) {
    fail("not logged in. Run `claude-console auth login <email>`.");
  }

  const { data, error } = await client.auth.setSession({
    access_token: state.session.accessToken,
    refresh_token: state.session.refreshToken,
  });
  if (error || !data.session) {
    fail(
      `session expired or invalid (${error?.message ?? "no session"}). ` +
        "Run `claude-console auth login` again.",
    );
  }

  if (data.session.access_token !== state.session.accessToken) {
    state.session = {
      email: data.session.user.email ?? state.session.email,
      userId: data.session.user.id,
      accessToken: data.session.access_token,
      refreshToken: data.session.refresh_token,
      expiresAt: data.session.expires_at ?? null,
    };
    saveState(state);
  }

  return { client, userId: data.session.user.id };
}
