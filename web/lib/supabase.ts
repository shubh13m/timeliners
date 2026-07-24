import { createClient, SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  throw new Error(
    "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY. Set them in web/.env.local (and in GitHub Secrets for deploy)."
  );
}

let browserClient: SupabaseClient | null = null;

export function supabaseBrowser(): SupabaseClient {
  if (browserClient) return browserClient;
  browserClient = createClient(url!, anonKey!, {
    auth: { persistSession: false },
  });
  return browserClient;
}

/** Fresh client (no singleton) — use at build time for SSG data fetches. */
export function supabaseBuild(): SupabaseClient {
  return createClient(url!, anonKey!, { auth: { persistSession: false } });
}
