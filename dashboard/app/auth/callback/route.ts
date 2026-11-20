import { NextResponse, type NextRequest } from "next/server";
import { serverClient } from "@/lib/supabase/server";

// Magic-link landing: swap the one-time code for a session cookie, then go to the queue.
export async function GET(req: NextRequest) {
  const code = req.nextUrl.searchParams.get("code");
  const to = new URL("/", req.nextUrl.origin);
  if (code) {
    const sb = await serverClient();
    const { error } = await sb.auth.exchangeCodeForSession(code);
    if (error) to.pathname = "/login";
  } else {
    to.pathname = "/login";
  }
  return NextResponse.redirect(to);
}
