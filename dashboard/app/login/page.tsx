"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { IS_DEMO } from "@/lib/env";
import { browserClient } from "@/lib/supabase/client";

/** Owner-only sign in (D054): email magic link, no sign-ups. Unknown emails get the same answer. */
export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  // Reason passed back by /auth/callback when a link fails.
  useEffect(() => { setErr(new URLSearchParams(window.location.search).get("error")); }, []);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    const { error } = await browserClient().auth.signInWithOtp({
      email: email.trim(),
      options: { shouldCreateUser: false, emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    setBusy(false);
    // Same message for unknown emails so the page does not reveal who has an account.
    if (error && !/signups not allowed|not found|otp_disabled/i.test(error.message)) setErr(error.message);
    else setSent(true);
  };

  // Cross-device sign in: type the 6-digit code from the email (works even when
  // the link opens on another device, where the link itself cannot finish).
  const verify = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    const { error } = await browserClient().auth.verifyOtp({ email: email.trim(), token: code.trim(), type: "email" });
    setBusy(false);
    if (error) setErr(error.message);
    else window.location.assign("/");
  };

  return (
    <main className="gate">
      <form className="gate-card" onSubmit={sent ? verify : send}>
        <span className="mk"><Icon name="bolt" size={22} /></span>
        <h1>Clipp</h1>
        {IS_DEMO ? (
          <>
            <p>Demo mode is on, so there is nothing to sign in to.</p>
            <Link className="btn light" href="/">Open the demo</Link>
          </>
        ) : sent ? (
          <>
            <p>If that email belongs to the owner, a sign-in email is on its way. Open its link on this device, or type the code from it here.</p>
            <label htmlFor="code" className="sr-only">Code</label>
            <input id="code" inputMode="numeric" autoComplete="one-time-code" placeholder="6-digit code"
              value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 10))} />
            <button className="btn light" disabled={busy || code.length < 6}>{busy ? "Checking…" : "Sign in with code"}</button>
            {err && <p className="err" role="alert">{err}</p>}
          </>
        ) : (
          <>
            <p>Private. Owner only.</p>
            <label htmlFor="email" className="sr-only">Email</label>
            <input id="email" type="email" autoComplete="email" required placeholder="you@email.com"
              value={email} onChange={(e) => setEmail(e.target.value)} />
            <button className="btn light" disabled={busy || !email}>{busy ? "Sending…" : "Email me a link"}</button>
            {err && <p className="err" role="alert">{err}</p>}
          </>
        )}
      </form>
    </main>
  );
}
