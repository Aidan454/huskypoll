// Small panel that proves the frontend can talk to the backend API.
// Drop it on any page:  import BackendStatus from "../components/BackendStatus.jsx";
//                       <BackendStatus />
//
// It calls:
//   GET  /api/health          -> the server is up and can reach the database
//   GET  /api/me              -> who is logged in (401 = nobody yet, still a valid answer)
//   POST /api/auth/dev-login  -> optional button; only works with HUSKYPOLL_DEV_LOGIN=1
//
// The API address comes from VITE_API_BASE (set in compose.yml), falling back to
// http://localhost:8000/api for `npm run dev` without Docker.
import { useCallback, useEffect, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://localhost:8000/api").replace(/\/$/, "");

// credentials: "include" sends/receives the login cookie across ports (5173 -> 8000)
async function call(path, options = {}) {
  const started = performance.now();
  const resp = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const ms = Math.round(performance.now() - started);
  let body = null;
  try {
    body = await resp.json();
  } catch {
    // some responses have no body
  }
  return { status: resp.status, ok: resp.ok, body, ms };
}

export default function BackendStatus() {
  const [health, setHealth] = useState({ state: "checking" });
  const [me, setMe] = useState({ state: "checking" });

  const check = useCallback(async () => {
    setHealth({ state: "checking" });
    setMe({ state: "checking" });
    try {
      const h = await call("/health");
      setHealth(h.ok && h.body?.ok ? { state: "ok", ms: h.ms } : { state: "error", detail: `HTTP ${h.status}` });
    } catch (err) {
      // fetch throws (no HTTP status at all) when the server is down or CORS blocks it
      setHealth({ state: "error", detail: `Can't reach ${API_BASE} (${err.message}). Is the backend running?` });
      setMe({ state: "error", detail: "skipped" });
      return;
    }
    try {
      const m = await call("/me");
      if (m.ok) setMe({ state: "ok", user: m.body });
      else if (m.status === 401) setMe({ state: "anonymous" });
      else setMe({ state: "error", detail: `HTTP ${m.status}: ${m.body?.detail ?? ""}` });
    } catch (err) {
      setMe({ state: "error", detail: err.message });
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- first check on mount
    check();
  }, [check]);

  async function devLogin() {
    try {
      const r = await call("/auth/dev-login", {
        method: "POST",
        body: JSON.stringify({
          email: "pat.prof@uconn.edu", net_id: "prf00001", first_name: "Pat", last_name: "Prof", role: "instructor",
        }),
      });
      if (r.status === 404) {
        setMe({ state: "error", detail: "Developer login is off (set HUSKYPOLL_DEV_LOGIN=1 on the backend)" });
        return;
      }
      if (!r.ok) {
        setMe({ state: "error", detail: `HTTP ${r.status}: ${r.body?.detail ?? ""}` });
        return;
      }
      check(); // re-read /me: if the cookie works, it now shows the user
    } catch (err) {
      setMe({ state: "error", detail: err.message });
    }
  }

  async function logout() {
    try {
      await call("/auth/logout", { method: "POST" });
    } finally {
      check();
    }
  }

  return (
    <section style={styles.box}>
      <h3 style={styles.title}>Backend connection</h3>
      <p style={styles.api}>API: <code>{API_BASE}</code></p>

      <Row label="Server + database">
        {health.state === "checking" && <span>Checking…</span>}
        {health.state === "ok" && <span style={styles.good}>✔ Connected ({health.ms} ms)</span>}
        {health.state === "error" && <span style={styles.bad}>✘ {health.detail}</span>}
      </Row>

      <Row label="Logged in as">
        {me.state === "checking" && <span>Checking…</span>}
        {me.state === "anonymous" && <span>Nobody yet (the backend answered 401, which is expected)</span>}
        {me.state === "ok" && (
          <span style={styles.good}>
            ✔ {me.user.display_name} ({me.user.net_id}, {me.user.role})
          </span>
        )}
        {me.state === "error" && <span style={styles.bad}>✘ {me.detail}</span>}
      </Row>

      <div style={styles.buttons}>
        <button onClick={check}>Check again</button>
        {me.state === "ok" ? (
          <button onClick={logout}>Log out</button>
        ) : (
          <button onClick={devLogin} disabled={health.state !== "ok"}>Dev login as instructor</button>
        )}
      </div>
    </section>
  );
}

function Row({ label, children }) {
  return (
    <p style={styles.row}>
      <strong>{label}:</strong> {children}
    </p>
  );
}

const styles = {
  box: { border: "1px solid #ccc", borderRadius: 8, padding: "12px 16px", margin: "16px 0", maxWidth: 560, textAlign: "left" },
  title: { margin: "0 0 8px" },
  api: { margin: "0 0 8px", fontSize: "0.85em", opacity: 0.8 },
  row: { margin: "4px 0" },
  good: { color: "#1a7f37" },
  bad: { color: "#cf222e" },
  buttons: { display: "flex", gap: 8, marginTop: 8 },
};
