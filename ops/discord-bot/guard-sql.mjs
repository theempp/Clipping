// PreToolUse hook: only plain read-only SQL may run unattended from Discord.
// Anything else is denied (never "ask": nobody is at the keyboard).
let raw = "";
process.stdin.on("data", (d) => (raw += d));
process.stdin.on("end", () => {
  let q = "";
  try {
    q = String(JSON.parse(raw).tool_input?.query ?? "");
  } catch {}
  const s = q.replace(/--.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "").trim();
  const readOnly =
    /^(select|with|explain)\b/i.test(s) &&
    !/;\s*\S/.test(s) &&
    !/\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy|call|do|merge|vacuum|set|reset|lock|refresh|comment)\b/i.test(s);
  const out = readOnly
    ? { hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision: "allow" } }
    : {
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "deny",
          permissionDecisionReason: "Discord bot is read-only: single SELECT/WITH/EXPLAIN only.",
        },
      };
  process.stdout.write(JSON.stringify(out));
});
