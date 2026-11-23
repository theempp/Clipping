"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
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
    <>
      <div className="z-amb" aria-hidden="true" /><div className="z-grid" aria-hidden="true" />
      <main className="z-gate">
        <form className="z-popbx z-sm" onSubmit={sent ? verify : send} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="z-brand"><span className="z-mk">Z</span><div>Zwoclippe<small>Private · owner only</small></div></div>
          {IS_DEMO ? (
            <>
              <p className="z-mut" style={{ margin: 0 }}>Demo mode is on, so there is nothing to sign in to.</p>
              <Link className="z-btn z-w" href="/" style={{ justifyContent: "center" }}>Open the demo</Link>
            </>
          ) : sent ? (
            <>
              <p className="z-mut" style={{ margin: 0 }}>If that email belongs to the owner, a sign-in email is on its way. Open its link on this device, or type the code from it here.</p>
              <label htmlFor="code" className="z-lbl">Code</label>
              <input id="code" className="z-fld" inputMode="numeric" autoComplete="one-time-code" placeholder="6-digit code"
                value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 10))} />
              <button className="z-btn z-w" style={{ justifyContent: "center" }} disabled={busy || code.length < 6}>{busy ? "Checking…" : "Sign in with code"}</button>
              {err && <p className="z-note z-bad" role="alert">{err}</p>}
            </>
          ) : (
            <>
              <label htmlFor="email" className="z-lbl">Email</label>
              <input id="email" className="z-fld" type="email" autoComplete="email" required placeholder="you@email.com"
                value={email} onChange={(e) => setEmail(e.target.value)} />
              <button className="z-btn z-w" style={{ justifyContent: "center" }} disabled={busy || !email}>{busy ? "Sending…" : "Email me a link"}</button>
              {err && <p className="z-note z-bad" role="alert">{err}</p>}
            </>
          )}
        </form>
      </main>
    </>
  );
}
