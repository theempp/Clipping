import { NextResponse, type NextRequest } from "next/server";
import type { EmailOtpType } from "@supabase/supabase-js";
import { serverClient } from "@/lib/supabase/server";

// Magic-link landing. Handles both link styles Supabase can send:
// ?code=... (PKCE, must open in the browser that asked for the link) and
// ?token_hash=...&type=... (works in any browser). On failure the login page
// shows the reason instead of a bare error.
export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams;
  const to = new URL("/", req.nextUrl.origin);
  const fail = (reason: string) => {
    to.pathname = "/login";
    to.searchParams.set("error", reason);
    return NextResponse.redirect(to);
  };
  const upstream = q.get("error_description") || q.get("error");
  if (upstream) return fail(upstream);

  const sb = await serverClient();
  const code = q.get("code");
  const tokenHash = q.get("token_hash");
  if (tokenHash) {
    const { error } = await sb.auth.verifyOtp({ token_hash: tokenHash, type: (q.get("type") || "email") as EmailOtpType });
    if (error) return fail(error.message);
  } else if (code) {
    const { error } = await sb.auth.exchangeCodeForSession(code);
    if (error) return fail(/verifier/i.test(error.message)
      ? "Open the link in the same browser where you asked for it."
      : error.message);
  } else {
    return fail("Login link was incomplete. Ask for a new one.");
  }
  return NextResponse.redirect(to);
}
