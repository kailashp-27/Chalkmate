import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const supabase = url && key ? createClient(url, key) : null;

// Only the local Supabase development instance uses the captured mail inbox.
export const localInboxUrl = (() => {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (
      !["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname) ||
      parsed.port !== "54321"
    )
      return null;
    parsed.port = "54324";
    return parsed.origin;
  } catch {
    return null;
  }
})();
