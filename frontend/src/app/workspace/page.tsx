"use client";

import { useEffect, useState, type FormEvent } from "react";

const base = process.env.NEXT_PUBLIC_MOSIP_API_BASE ?? "http://localhost:8000";
type Organization = { id: number; name: string; role: string };
type Investigation = { id: string; event_id: number; status: string; query: string; result?: { conclusion: string; evidence: { source: string; external_id: string }; limitations: string[] }; steps?: { tool: string; status: string }[]; error?: string };
type EventRecord = { id: number; source: string; external_id: string; primary_norad: number | null; secondary_norad: number | null; tca: string; miss_distance_m: number | null; collision_probability: number | null; status: string };
type Asset = { id: number; norad_id: number | null; display_name: string; constellation: string | null; epoch_time: string | null };

async function api<T>(path: string, token: string | null, method = "GET", body?: object): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = error.detail;
    const message = typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map(item => typeof item?.msg === "string" ? item.msg : "Invalid field").join("; ")
      : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}

export default function WorkspacePage() {
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [register, setRegister] = useState(false);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [orgName, setOrgName] = useState("");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedJob, setSelectedJob] = useState<Investigation | null>(null);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [eventSource, setEventSource] = useState("");
  const [eventId, setEventId] = useState("");
  const [tca, setTca] = useState("");
  const [miss, setMiss] = useState("");
  const [assetName, setAssetName] = useState("");
  const [norad, setNorad] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadOrganizations(auth: string) {
    const list = await api<Organization[]>("/organizations", auth);
    setOrganizations(list);
    setSelected(current => current && list.some(item => item.id === current) ? current : list[0]?.id ?? null);
  }
  async function loadAssets(org: number, auth: string) {
    const result = await api<{items: Asset[]}>(`/organizations/${org}/fleet`, auth);
    setAssets(result.items);
    setEvents(await api<EventRecord[]>(`/organizations/${org}/events`, auth));
    setInvestigations(await api<Investigation[]>(`/organizations/${org}/investigations`, auth));
  }
  useEffect(() => {
    const saved = sessionStorage.getItem("astrocomply_session");
    if (saved) void Promise.resolve().then(() => { setToken(saved); return loadOrganizations(saved); }).catch(() => { sessionStorage.removeItem("astrocomply_session"); setToken(null); });
  }, []);
  useEffect(() => { if (selected && token) void Promise.resolve().then(() => loadAssets(selected, token)).catch(e => setError(String(e))); }, [selected, token]);
  useEffect(() => { if (selected) sessionStorage.setItem("astrocomply_organization", String(selected)); }, [selected]);

  async function signIn(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await api<{access_token: string}>(register ? "/auth/register" : "/auth/login", null, "POST", { email, password });
      sessionStorage.setItem("astrocomply_session", result.access_token);
      setToken(result.access_token); setPassword("");
      await loadOrganizations(result.access_token);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Sign in failed"); }
    finally { setBusy(false); }
  }
  async function createOrganization(event: FormEvent) {
    event.preventDefault(); if (!token) return; setBusy(true); setError("");
    try {
      const result = await api<Organization>("/organizations", token, "POST", { name: orgName });
      await loadOrganizations(token); setSelected(result.id); setOrgName("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create workspace"); }
    finally { setBusy(false); }
  }
  async function addAsset(event: FormEvent) {
    event.preventDefault(); if (!token || !selected) return; setBusy(true); setError("");
    try {
      await api(`/organizations/${selected}/fleet`, token, "POST", { display_name: assetName, norad_id: norad ? Number(norad) : null });
      await loadAssets(selected, token); setAssetName(""); setNorad("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not add asset"); }
    finally { setBusy(false); }
  }
  async function uploadCdm(file: File) {
    if (!token || !selected) return;
    setBusy(true); setError("");
    try {
      const form = new FormData(); form.append("file", file);
      const response = await fetch(`${base}/organizations/${selected}/events/cdm`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form,
      });
      if (!response.ok) {
        const detail = await response.json();
        throw new Error(detail.detail ?? `CDM upload failed (${response.status})`);
      }
      await loadAssets(selected, token);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not import CDM"); }
    finally { setBusy(false); }
  }
  async function importEvent(event: FormEvent) {
    event.preventDefault(); if (!token || !selected) return; setBusy(true); setError("");
    try {
      await api(`/organizations/${selected}/events`, token, "POST", { source: eventSource, external_id: eventId, tca: new Date(tca).toISOString(), miss_distance_m: miss ? Number(miss) : null });
      await loadAssets(selected, token); setEventSource(""); setEventId(""); setTca(""); setMiss("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not import event"); }
    finally { setBusy(false); }
  }
  async function investigate(eventId: number) {
    if (!token || !selected) return; setBusy(true); setError("");
    try {
      const job = await api<Investigation>(`/organizations/${selected}/investigations`, token, "POST", { event_id: eventId, query: "Investigate provider evidence and uncertainty" });
      setSelectedJob(job); await loadAssets(selected, token);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not queue investigation"); }
    finally { setBusy(false); }
  }
  async function downloadReport(jobId: string) {
    if (!token || !selected) return;
    try {
      const response = await fetch(`${base}/organizations/${selected}/investigations/${jobId}/report`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(`Report unavailable (${response.status})`);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a"); link.href = url; link.download = `astrocomply-investigation-${jobId}.txt`;
      link.click(); URL.revokeObjectURL(url);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not download report"); }
  }
  async function downloadCsv(kind: "fleet" | "events") {
    if (!token || !selected) return;
    try {
      const response = await fetch(`${base}/organizations/${selected}/reports/${kind}.csv`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(`Export unavailable (${response.status})`);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a"); link.href = url;
      link.download = `astrocomply-${kind}-${selected}.csv`;
      link.click(); URL.revokeObjectURL(url);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not export CSV"); }
  }
  async function inspectJob(jobId: string) {
    if (!token || !selected) return;
    try { setSelectedJob(await api<Investigation>(`/organizations/${selected}/investigations/${jobId}`, token)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not inspect investigation"); }
  }
  async function setEventStatus(id: number, status: string) {
    if (!token || !selected) return; setError("");
    try { await api(`/organizations/${selected}/events/${id}`, token, "PATCH", { status }); await loadAssets(selected, token); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update event"); }
  }
  async function signOut() {
    if (token) await api("/auth/logout", token, "POST").catch(() => undefined);
    sessionStorage.removeItem("astrocomply_session"); sessionStorage.removeItem("astrocomply_organization"); setToken(null); setOrganizations([]); setAssets([]);
  }
  return <main className="min-h-full bg-[#080c12] p-6 text-slate-100 lg:p-10">
    <header className="mb-8 border-b border-slate-700 pb-5"><p className="text-xs uppercase tracking-[0.3em] text-cyan-300">AstroComply Operations</p><h1 className="mt-2 text-3xl font-semibold">Workspace and fleet</h1></header>
    {error && <p role="alert" className="mb-5 border border-red-500 p-3 text-red-300">{error}</p>}
    {!token ? <form onSubmit={signIn} className="max-w-md space-y-4">
      <h2 className="text-xl">{register ? "Create account" : "Sign in"}</h2>
      <label className="block">Email<input required type="email" value={email} onChange={e => setEmail(e.target.value)} className="mt-1 w-full border border-slate-600 bg-slate-900 p-3" /></label>
      <label className="block">Password<input required minLength={12} type="password" value={password} onChange={e => setPassword(e.target.value)} className="mt-1 w-full border border-slate-600 bg-slate-900 p-3" /></label>
      <button disabled={busy} className="bg-cyan-300 px-5 py-3 font-semibold text-black">{register ? "Register" : "Sign in"}</button>
      <button type="button" onClick={() => setRegister(!register)} className="ml-4 text-cyan-300">{register ? "Use existing account" : "Create account"}</button>
    </form> : <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-4"><label>Organization <select value={selected ?? ""} onChange={e => setSelected(Number(e.target.value))} className="ml-3 bg-slate-900 p-2">{organizations.map(org => <option key={org.id} value={org.id}>{org.name} · {org.role}</option>)}</select></label><button onClick={signOut} className="border border-slate-600 px-4 py-2">Sign out</button></div>
      <form onSubmit={createOrganization} className="flex flex-wrap gap-3"><input required minLength={2} maxLength={120} value={orgName} onChange={e => setOrgName(e.target.value)} placeholder="New organization" aria-label="New organization" className="border border-slate-600 bg-slate-900 p-3" /><button disabled={busy} className="bg-cyan-300 px-4 py-3 text-black">Create organization</button></form>
      {selected && <section><h2 className="mb-4 text-xl">Fleet assets</h2><button type="button" onClick={() => void downloadCsv("fleet")} className="mb-3 border border-cyan-500 px-3 py-2 text-sm text-cyan-300">Export fleet CSV</button><form onSubmit={addAsset} className="mb-5 flex flex-wrap gap-3"><input required value={assetName} onChange={e => setAssetName(e.target.value)} placeholder="Asset name" aria-label="Asset name" className="border border-slate-600 bg-slate-900 p-3" /><input inputMode="numeric" value={norad} onChange={e => setNorad(e.target.value)} placeholder="NORAD ID (optional)" aria-label="NORAD ID" className="border border-slate-600 bg-slate-900 p-3" /><button disabled={busy} className="bg-cyan-300 px-4 py-3 text-black">Add asset</button></form>{assets.length === 0 ? <p className="text-slate-400">No assets yet. Add one to start your fleet.</p> : <div className="overflow-x-auto"><table className="w-full border-collapse text-left"><thead><tr className="border-b border-slate-600 text-slate-400"><th className="p-3">Asset</th><th>NORAD</th><th>Constellation</th><th>Catalogue epoch</th></tr></thead><tbody>{assets.map(asset => <tr key={asset.id} className="border-b border-slate-800"><td className="p-3">{asset.display_name}</td><td>{asset.norad_id ?? "Customer record"}</td><td>{asset.constellation ?? "—"}</td><td>{asset.epoch_time ?? "No catalogue match"}</td></tr>)}</tbody></table></div>}</section>}
      {selected && <section className="border-t border-slate-700 pt-6"><h2 className="mb-4 text-xl">Conjunction events</h2><button type="button" onClick={() => void downloadCsv("events")} className="mb-3 border border-cyan-500 px-3 py-2 text-sm text-cyan-300">Export events CSV</button><p className="mb-4 text-sm text-slate-400">Import provider supplied event values. Collision probability remains unavailable without validated uncertainty.</p><label className="mb-5 block text-sm">Upload a CCSDS CDM KVN file<input type="file" accept=".cdm,.kvn,.txt" disabled={busy} onChange={e => { const file = e.target.files?.[0]; if (file) void uploadCdm(file); }} className="mt-2 block" /></label><form onSubmit={importEvent} className="mb-5 flex flex-wrap gap-3"><input required value={eventSource} onChange={e => setEventSource(e.target.value)} placeholder="Source" aria-label="Event source" className="border border-slate-600 bg-slate-900 p-3" /><input required value={eventId} onChange={e => setEventId(e.target.value)} placeholder="Provider event ID" aria-label="Provider event ID" className="border border-slate-600 bg-slate-900 p-3" /><input required type="datetime-local" value={tca} onChange={e => setTca(e.target.value)} aria-label="Closest approach time" className="border border-slate-600 bg-slate-900 p-3" /><input type="number" min="0" step="any" value={miss} onChange={e => setMiss(e.target.value)} placeholder="Miss distance (m)" aria-label="Miss distance in metres" className="border border-slate-600 bg-slate-900 p-3" /><button disabled={busy} className="bg-cyan-300 px-4 py-3 text-black">Import event</button></form>{events.length === 0 ? <p className="text-slate-400">No events imported.</p> : <ul className="space-y-2">{events.map(item => <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 border border-slate-700 p-3"><div><strong>{item.external_id}</strong><p className="text-sm text-slate-400">{item.source} · TCA {item.tca} · Miss {item.miss_distance_m ?? "unknown"} m · Pc {item.collision_probability ?? "insufficient data"}</p></div><button type="button" disabled={busy} onClick={() => void investigate(item.id)} className="border border-cyan-500 px-3 py-2 text-cyan-300">Investigate</button><select value={item.status} onChange={e => void setEventStatus(item.id, e.target.value)} aria-label={`Status for ${item.external_id}`} className="bg-slate-900 p-2"><option value="unverified">Unverified</option><option value="review">In review</option><option value="resolved">Resolved</option></select></li>)}</ul>}</section>}
      {selected && <section className="border-t border-slate-700 pt-6"><h2 className="mb-3 text-xl">Investigation history</h2>{investigations.length === 0 ? <p className="text-slate-400">No investigations submitted.</p> : <ul className="space-y-2">{investigations.map(job => <li key={job.id}><button type="button" onClick={() => void inspectJob(job.id)} className="text-cyan-300 underline">{job.query} · {job.status}</button></li>)}</ul>}{selectedJob && <div className="mt-5 border border-slate-700 p-4"><button type="button" onClick={() => void inspectJob(selectedJob.id)} className="mb-3 border border-slate-600 px-3 py-2">Refresh status</button><p>{selectedJob.status}</p>{selectedJob.error && <p role="alert">{selectedJob.error}</p>}{selectedJob.steps?.map((step,index) => <p key={index} className="text-sm text-slate-400">{step.tool} · {step.status}</p>)}{selectedJob.result && <><p className="mt-3">{selectedJob.result.conclusion}</p><p className="text-sm text-slate-400">Evidence {selectedJob.result.evidence.source} / {selectedJob.result.evidence.external_id}</p><button type="button" onClick={() => void downloadReport(selectedJob.id)} className="mt-3 border border-cyan-500 px-3 py-2 text-cyan-300">Download report</button></>}</div>}</section>}
    </div>}
  </main>;
}
