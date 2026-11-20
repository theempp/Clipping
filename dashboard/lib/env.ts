// Demo mode = no Supabase keys, or forced with NEXT_PUBLIC_CLIPP_DEMO=1 (D057).
export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
export const IS_DEMO =
  process.env.NEXT_PUBLIC_CLIPP_DEMO === "1" || !SUPABASE_URL || !SUPABASE_ANON_KEY;
export const PC_NAME = process.env.NEXT_PUBLIC_PC_NAME || "Daddys";
