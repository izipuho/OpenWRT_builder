const API = "http://10.8.25.110:8080/api/v1";
const API_BASE = API.replace(/\/api\/v1\/?$/, "");

const templateCache = {
    list: null,
    profile: null,
};

const el = (id) => document.getElementById(id);

function setTab(tab) {
    ["builds", "lists", "profiles", "files"].forEach((name) => {
        const active = tab === name;
        el(`tab-${name}`).classList.toggle("active", active);
        el(`view-${name}`).classList.toggle("hidden", !active);
    });
}

async function apiJson(path, opts = {}) {
    const headers = { ...(opts.headers || {}) };
    if (opts.body && !(opts.body instanceof FormData) && !headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
    }

    const res = await fetch(path, {
        ...opts,
        headers,
    });

    const ct = res.headers.get("content-type") || "";
    const body = ct.includes("application/json") ? await res.json() : await res.text();

    if (!res.ok) {
        const msg = typeof body === "string" ? body : JSON.stringify(body);
        throw new Error(`${res.status} ${msg}`);
    }
    return body;
}

/* ---------------- Lists ---------------- */

function normalizeListTemplate(obj = {}) {
    const list = obj.list || {};
    return {
        name: typeof obj.name === "string" && obj.name.trim() ? obj.name : "New list",
        schema_version: Number(obj.schema_version) || 1,
        list: {
            include: Array.isArray(list.include) ? list.include.map(String) : [],
            exclude: Array.isArray(list.exclude) ? list.exclude.map(String) : [],
        },
    };
}

async function getTemplate({ cacheKey, examplePath, normalize, fallback }) {
    if (templateCache[cacheKey]) return templateCache[cacheKey];
    try {
        const res = await fetch(`${API_BASE}${examplePath}`);
        if (!res.ok) throw new Error(`template_http_${res.status}`);
        templateCache[cacheKey] = normalize(await res.json());
    } catch (_) {
        templateCache[cacheKey] = normalize(fallback);
    }
    return templateCache[cacheKey];
}

async function getListTemplate() {
    return getTemplate({
        cacheKey: "list",
        examplePath: "/examples/list.json",
        normalize: normalizeListTemplate,
        fallback: {
            name: "New list",
            schema_version: 1,
            list: { include: [], exclude: [] },
        },
    });
}

function arrayToLines(items) {
    return (items || []).map((v) => String(v)).join("\n");
}

function linesToArray(text) {
    return String(text || "")
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
}

function timestampToMs(value) {
    const raw = String(value || "").trim();
    if (!raw) return Number.NaN;
    return Date.parse(raw);
}

function formatDateTime(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    const ts = timestampToMs(raw);
    if (Number.isNaN(ts)) return raw;
    return new Intl.DateTimeFormat(undefined, {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    }).format(new Date(ts));
}

function renderUpdatedAtCell(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    const ts = timestampToMs(raw);
    const sortTs = Number.isNaN(ts) ? "" : String(ts);
    return `<time datetime="${escapeAttr(raw)}" data-sort-ts="${escapeAttr(sortTs)}">${escapeHtml(formatDateTime(raw))}</time>`;
}

function sortByUpdatedAtDesc(rows) {
    return [...(rows || [])].sort((a, b) => {
        const aTs = timestampToMs(a?.updated_at);
        const bTs = timestampToMs(b?.updated_at);
        if (!Number.isNaN(aTs) && !Number.isNaN(bTs)) return bTs - aTs;
        if (!Number.isNaN(aTs)) return -1;
        if (!Number.isNaN(bTs)) return 1;
        return String(b?.updated_at || "").localeCompare(String(a?.updated_at || ""));
    });
}

function renderListsTable(rows) {
    const sortedRows = sortByUpdatedAtDesc(rows);
    const html = `
    <table>
      <thead>
        <tr><th>id</th><th>name</th><th>updated_at</th><th></th></tr>
      </thead>
      <tbody>
        ${sortedRows.map((r) => {
        const id = r.list_id ?? r.id ?? "";
        return `
          <tr>
            <td>${escapeHtml(id)}</td>
            <td>${escapeHtml(r.name ?? "")}</td>
            <td>${renderUpdatedAtCell(r.updated_at)}</td>
            <td class="actions">
              <button type="button" data-act="edit" data-id="${escapeAttr(id)}">Edit</button>
              <button type="button" data-act="del" data-id="${escapeAttr(id)}">Delete</button>
            </td>
          </tr>
        `;
    }).join("")}
      </tbody>
    </table>
  `;
    el("lists-table").innerHTML = html;

    el("lists-table").querySelectorAll("button").forEach((b) => {
        b.addEventListener("click", async () => {
            const id = b.getAttribute("data-id");
            const act = b.getAttribute("data-act");
            if (act === "edit") await openListEditor(id);
            if (act === "del") await deleteList(id);
        });
    });
}

async function refreshLists() {
    const rows = await apiJson(`${API}/lists`);
    renderListsTable(rows);
}

function showListsEditor(html) {
    el("lists-editor").innerHTML = html;
    el("lists-editor").classList.remove("hidden");
}

function hideListsEditor() {
    el("lists-editor").classList.add("hidden");
    el("lists-editor").innerHTML = "";
}

function listEditorHtml(id, model) {
    const includeText = arrayToLines(model?.list?.include);
    const excludeText = arrayToLines(model?.list?.exclude);
    const schemaVersion = Number(model?.schema_version) || 1;
    const name = model?.name || "";
    return `
    <h2>${id ? "Edit list" : "Create list"}</h2>
    ${id ? `
      <div class="row"><label>id</label><input id="list-id" value="${escapeAttr(id)}" disabled /></div>
    ` : `
      <div class="row"><label>list_id (optional)</label><input id="list-id" placeholder="slug" /></div>
    `}
    <div class="row"><label>name</label><input id="list-name" value="${escapeAttr(name)}" /></div>
    <div class="row"><label>include (one per line)</label><textarea id="list-include" rows="8">${escapeHtml(includeText)}</textarea></div>
    <div class="row"><label>exclude (one per line)</label><textarea id="list-exclude" rows="8">${escapeHtml(excludeText)}</textarea></div>
    <input id="list-schema-version" type="hidden" value="${escapeAttr(schemaVersion)}" />
    <div class="row buttons">
      <button id="list-save" type="button">Save</button>
      <button id="list-cancel" type="button">Cancel</button>
    </div>
    <pre id="list-error" class="error hidden"></pre>
  `;
}

async function openListEditor(id = null) {
    if (id) {
        const obj = await apiJson(`${API}/list/${encodeURIComponent(id)}`);
        showListsEditor(listEditorHtml(id, obj));
        wireListEditor(id);
    } else {
        const tpl = await getListTemplate();
        showListsEditor(listEditorHtml("", tpl));
        wireListEditor(null);
    }
}

function wireCrudEditor({
    cancelId,
    saveId,
    errorId,
    onCancel,
    collectBody,
    saveExisting,
    saveNew,
    afterSuccess,
}) {
    el(cancelId).addEventListener("click", onCancel);

    el(saveId).addEventListener("click", async () => {
        try {
            el(errorId).classList.add("hidden");
            const payload = collectBody();

            if (payload.existingId) {
                await saveExisting(payload);
            } else {
                await saveNew(payload);
            }

            await afterSuccess();
        } catch (e) {
            el(errorId).textContent = String(e.message || e);
            el(errorId).classList.remove("hidden");
        }
    });
}

function wireListEditor(existingId) {
    wireCrudEditor({
        cancelId: "list-cancel",
        saveId: "list-save",
        errorId: "list-error",
        onCancel: hideListsEditor,
        collectBody: () => {
            const id = el("list-id").value.trim();
            const name = el("list-name").value.trim();
            const schemaVersion = Number(el("list-schema-version").value) || 1;
            const include = linesToArray(el("list-include").value);
            const exclude = linesToArray(el("list-exclude").value);
            return {
                existingId,
                id,
                name,
                schema_version: schemaVersion,
                list: {
                    include,
                    exclude,
                },
            };
        },
        saveExisting: async (payload) => {
            await apiJson(`${API}/list/${encodeURIComponent(payload.existingId)}`, {
                method: "PUT",
                body: JSON.stringify({
                    name: payload.name,
                    schema_version: payload.schema_version,
                    list: payload.list,
                }),
            });
        },
        saveNew: async (payload) => {
            await apiJson(`${API}/list`, {
                method: "POST",
                body: JSON.stringify({
                    list_id: payload.id || undefined,
                    name: payload.name,
                    schema_version: payload.schema_version,
                    list: payload.list,
                }),
            });
        },
        afterSuccess: async () => {
            hideListsEditor();
            await refreshLists();
        },
    });
}

async function deleteList(id) {
    await apiJson(`${API}/list/${encodeURIComponent(id)}`, { method: "DELETE" });
    await refreshLists();
}

/* ---------------- Profiles ---------------- */

function normalizeProfileTemplate(obj = {}) {
    const profile = obj.profile || {};
    return {
        name: typeof obj.name === "string" && obj.name.trim() ? obj.name : "New profile",
        schema_version: Number(obj.schema_version) || 1,
        profile: {
            lists: Array.isArray(profile.lists) ? profile.lists.map(String) : [],
            extra_include: Array.isArray(profile.extra_include) ? profile.extra_include.map(String) : [],
            extra_exclude: Array.isArray(profile.extra_exclude) ? profile.extra_exclude.map(String) : [],
            files: Array.isArray(profile.files) ? profile.files.map(String) : [],
        },
    };
}

async function getProfileTemplate() {
    return getTemplate({
        cacheKey: "profile",
        examplePath: "/examples/profile.json",
        normalize: normalizeProfileTemplate,
        fallback: {
            name: "New profile",
            schema_version: 1,
            profile: { lists: [], extra_include: [], extra_exclude: [], files: [] },
        },
    });
}

async function getListChoices() {
    const rows = await apiJson(`${API}/lists`);
    return rows
        .map((r) => {
            const id = String(r.list_id ?? r.id ?? "").trim();
            const name = String(r.name || "").trim();
            if (!id || !name) return null;
            return {
                id,
                title: name,
                meta: id,
            };
        })
        .filter(Boolean);
}

async function getFileChoices() {
    const rows = await apiJson(`${API}/files`);
    return rows
        .map((r) => {
            const path = String(r.path || "").trim();
            if (!path) return null;
            return {
                id: path,
                title: path,
                meta: typeof r.size === "number" ? `${r.size} bytes` : "",
            };
        })
        .filter(Boolean);
}

function checkedValues(group) {
    return Array.from(document.querySelectorAll(`input[data-group="${group}"]:checked`))
        .map((elx) => elx.value);
}

function checklistHtml(group, options, selected, emptyText = "No items available") {
    if (!options.length) return `<div class="muted">${escapeHtml(emptyText)}</div>`;
    const selectedSet = new Set(selected || []);
    return `
      <div class="checklist">
        ${options.map((o) => `
          <label class="checkitem">
            <input type="checkbox" data-group="${escapeAttr(group)}" value="${escapeAttr(o.id)}" ${selectedSet.has(o.id) ? "checked" : ""} />
            <span class="checktext">
              <span class="checktitle">${escapeHtml(o.title)}</span>
              ${o.meta ? `<span class="checkmeta">${escapeHtml(o.meta)}</span>` : ""}
            </span>
          </label>
        `).join("")}
      </div>
    `;
}

function renderProfilesTable(rows) {
    const sortedRows = sortByUpdatedAtDesc(rows);
    const html = `
    <table>
      <thead>
        <tr><th>id</th><th>name</th><th>updated_at</th><th></th></tr>
      </thead>
      <tbody>
        ${sortedRows.map((r) => {
        const id = r.profile_id ?? r.id ?? "";
        return `
            <tr>
              <td>${escapeHtml(id)}</td>
              <td>${escapeHtml(r.name ?? "")}</td>
              <td>${renderUpdatedAtCell(r.updated_at)}</td>
              <td class="actions">
                <button type="button" data-act="edit" data-id="${escapeAttr(id)}">Edit</button>
                <button type="button" data-act="del" data-id="${escapeAttr(id)}">Delete</button>
              </td>
            </tr>
          `;
    }).join("")}
      </tbody>
    </table>
  `;
    el("profiles-table").innerHTML = html;

    el("profiles-table").querySelectorAll("button").forEach((b) => {
        b.addEventListener("click", async () => {
            const id = b.getAttribute("data-id");
            const act = b.getAttribute("data-act");
            if (act === "edit") await openProfileEditor(id);
            if (act === "del") await deleteProfile(id);
        });
    });
}

async function refreshProfiles() {
    const rows = await apiJson(`${API}/profiles`);
    renderProfilesTable(rows);
}

function showProfilesEditor(html) {
    el("profiles-editor").innerHTML = html;
    el("profiles-editor").classList.remove("hidden");
}

function hideProfilesEditor() {
    el("profiles-editor").classList.add("hidden");
    el("profiles-editor").innerHTML = "";
}

function profileEditorHtml(id, model, listOptions, fileOptions) {
    const profile = model?.profile || {};
    const selectedLists = Array.isArray(profile.lists) ? profile.lists : [];
    const selectedFiles = Array.isArray(profile.files) ? profile.files : [];
    const includeText = arrayToLines(Array.isArray(profile.extra_include) ? profile.extra_include : []);
    const excludeText = arrayToLines(Array.isArray(profile.extra_exclude) ? profile.extra_exclude : []);
    const schemaVersion = Number(model?.schema_version) || 1;
    const name = model?.name || "";
    const normalizedFileOptions = Array.isArray(fileOptions) ? fileOptions : [];
    const mergedFileOptions = [
        ...normalizedFileOptions,
        ...selectedFiles
            .filter((v) => !normalizedFileOptions.some((o) => o.id === v))
            .map((v) => ({ id: v, title: v, meta: "missing on disk" })),
    ];
    const defaultSelectedFiles = !id && selectedFiles.length === 0
        ? mergedFileOptions.map((o) => o.id)
        : selectedFiles;

    return `
    <h2>${id ? "Edit profile" : "Create profile"}</h2>
    ${id ? `
      <div class="row"><label>id</label><input id="profile-id" value="${escapeAttr(id)}" disabled /></div>
    ` : `
      <div class="row"><label>profile_id (optional)</label><input id="profile-id" placeholder="slug" /></div>
    `}
    <div class="row"><label>name</label><input id="profile-name" value="${escapeAttr(name)}" /></div>
    <div class="row"><label>lists</label>${checklistHtml("profile-lists", listOptions, selectedLists, "No lists available")}</div>
    <div class="row"><label>include (one per line)</label><textarea id="profile-include" rows="8">${escapeHtml(includeText)}</textarea></div>
    <div class="row"><label>exclude (one per line)</label><textarea id="profile-exclude" rows="8">${escapeHtml(excludeText)}</textarea></div>
    <div class="row"><label>files</label>${checklistHtml("profile-files", mergedFileOptions, defaultSelectedFiles, "No files uploaded")}</div>
    <input id="profile-schema-version" type="hidden" value="${escapeAttr(schemaVersion)}" />
    <div class="row buttons">
      <button id="profile-save" type="button">Save</button>
      <button id="profile-cancel" type="button">Cancel</button>
    </div>
    <pre id="profile-error" class="error hidden"></pre>
  `;
}

async function openProfileEditor(id = null) {
    const listOptions = await getListChoices();
    const fileOptions = await getFileChoices();
    if (id) {
        const obj = await apiJson(`${API}/profile/${encodeURIComponent(id)}`);
        const model = normalizeProfileTemplate(obj);
        showProfilesEditor(profileEditorHtml(id, model, listOptions, fileOptions));
        wireProfileEditor(id);
    } else {
        const model = await getProfileTemplate();
        showProfilesEditor(profileEditorHtml("", model, listOptions, fileOptions));
        wireProfileEditor(null);
    }
}

function wireProfileEditor(existingId) {
    wireCrudEditor({
        cancelId: "profile-cancel",
        saveId: "profile-save",
        errorId: "profile-error",
        onCancel: hideProfilesEditor,
        collectBody: () => {
            const id = el("profile-id").value.trim();
            const name = el("profile-name").value.trim();
            const schemaVersion = Number(el("profile-schema-version").value) || 1;
            const lists = checkedValues("profile-lists");
            const include = linesToArray(el("profile-include").value);
            const exclude = linesToArray(el("profile-exclude").value);
            const files = checkedValues("profile-files");
            return {
                existingId,
                id,
                name,
                schema_version: schemaVersion,
                profile: {
                    lists,
                    extra_include: include,
                    extra_exclude: exclude,
                    files,
                },
            };
        },
        saveExisting: async (payload) => {
            await apiJson(`${API}/profile/${encodeURIComponent(payload.existingId)}`, {
                method: "PUT",
                body: JSON.stringify({
                    name: payload.name,
                    schema_version: payload.schema_version,
                    profile: payload.profile,
                }),
            });
        },
        saveNew: async (payload) => {
            await apiJson(`${API}/profile`, {
                method: "POST",
                body: JSON.stringify({
                    profile_id: payload.id || undefined,
                    name: payload.name,
                    schema_version: payload.schema_version,
                    profile: payload.profile,
                }),
            });
        },
        afterSuccess: async () => {
            hideProfilesEditor();
            await refreshProfiles();
        },
    });
}

async function deleteProfile(id) {
    await apiJson(`${API}/profile/${encodeURIComponent(id)}`, { method: "DELETE" });
    await refreshProfiles();
}

/* ---------------- Builds ---------------- */

function showBuildsError(err = "") {
    const msg = String(err || "").trim();
    el("builds-error").textContent = msg;
    el("builds-error").classList.toggle("hidden", !msg);
}

function renderBuildProfileOptions(rows) {
    const select = el("builds-profile");
    const options = (rows || [])
        .map((r) => ({
            id: String(r.profile_id ?? r.id ?? "").trim(),
            name: String(r.name || "").trim(),
        }))
        .filter((r) => r.id);

    if (!options.length) {
        select.innerHTML = `<option value="">No profiles available</option>`;
        return;
    }

    select.innerHTML = options
        .map((opt) => `<option value="${escapeAttr(opt.id)}">${escapeHtml(opt.name || opt.id)} (${escapeHtml(opt.id)})</option>`)
        .join("");
}

function renderBuildVersionOptions(payload = {}) {
    const select = el("builds-version");
    const versions = Array.isArray(payload.latest)
        ? payload.latest.map((v) => String(v).trim()).filter(Boolean)
        : [];
    const latest = versions[0] || "";
    const current = String(select.value || "").trim();

    if (!versions.length) {
        select.innerHTML = `<option value="">No versions available</option>`;
        return;
    }

    const selected = versions.includes(current)
        ? current
        : (versions.includes(latest) ? latest : versions[0]);

    select.innerHTML = versions
        .map((v) => {
            const label = v === latest ? `${v} (latest)` : v;
            return `<option value="${escapeAttr(v)}" ${v === selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
        })
        .join("");
}

function renderBuildsTable(rows) {
    const sortedRows = sortByUpdatedAtDesc(rows);
    const html = `
    <table>
      <thead>
        <tr><th>build_id</th><th>state</th><th>progress</th><th>updated_at</th><th>message</th><th></th></tr>
      </thead>
      <tbody>
        ${sortedRows.map((r) => {
        const buildId = String(r.build_id || "");
        const state = String(r.state || "");
        const canStop = state === "running" && !r.cancel_requested;
        const canDelete = state !== "running";
        const canDownload = state === "done";
        return `
          <tr>
            <td>${escapeHtml(buildId)}</td>
            <td>${escapeHtml(state)}</td>
            <td>${escapeHtml(String(r.progress ?? ""))}%</td>
            <td>${renderUpdatedAtCell(r.updated_at)}</td>
            <td>${escapeHtml(r.message ?? "")}</td>
            <td class="actions">
              ${canStop ? `<button type="button" data-act="stop" data-id="${escapeAttr(buildId)}">Stop</button>` : ""}
              ${canDelete ? `<button type="button" data-act="delete" data-id="${escapeAttr(buildId)}">Delete</button>` : ""}
              ${canDownload ? `<button type="button" data-act="download" data-id="${escapeAttr(buildId)}">Download</button>` : ""}
            </td>
          </tr>
        `;
    }).join("")}
      </tbody>
    </table>
  `;
    el("builds-table").innerHTML = html;

    el("builds-table").querySelectorAll("button").forEach((b) => {
        b.addEventListener("click", async () => {
            const buildId = b.getAttribute("data-id");
            const act = b.getAttribute("data-act");
            if (act === "stop") {
                await cancelBuild(buildId);
            } else if (act === "delete") {
                await deleteBuild(buildId);
            } else if (act === "download") {
                window.open(`${API}/build/${encodeURIComponent(buildId)}/download`, "_blank");
            }
        });
    });
}

async function refreshBuilds() {
    showBuildsError("");
    const [profiles, builds, versionsPayload] = await Promise.all([
        apiJson(`${API}/profiles`),
        apiJson(`${API}/builds`),
        apiJson(`${API}/build-versions`).catch(() => ({ versions: [], latest: "" })),
    ]);
    renderBuildProfileOptions(profiles);
    renderBuildVersionOptions(versionsPayload);
    renderBuildsTable(builds);
}

async function createBuild() {
    showBuildsError("");
    const profileId = el("builds-profile").value.trim();
    const target = el("builds-target").value.trim();
    const subtarget = el("builds-subtarget").value.trim();
    const version = el("builds-version").value.trim();
    const forceRebuild = el("builds-force").checked;
    const debug = el("builds-debug").checked;

    if (!profileId) {
        showBuildsError("Select a profile");
        return;
    }
    if (!target) {
        showBuildsError("Target is required");
        return;
    }
    if (!subtarget) {
        showBuildsError("Subtarget is required");
        return;
    }
    if (!version) {
        showBuildsError("Version is required");
        return;
    }

    await apiJson(`${API}/build`, {
        method: "POST",
        body: JSON.stringify({
            request: {
                profile_id: profileId,
                target,
                subtarget,
                version,
                options: {
                    force_rebuild: forceRebuild,
                    debug,
                },
            },
        }),
    });
    await refreshBuilds();
}

async function cancelBuild(buildId) {
    showBuildsError("");
    await apiJson(`${API}/build/${encodeURIComponent(buildId)}/cancel`, { method: "POST" });
    await refreshBuilds();
}

async function deleteBuild(buildId) {
    showBuildsError("");
    await apiJson(`${API}/build/${encodeURIComponent(buildId)}`, { method: "DELETE" });
    await refreshBuilds();
}

/* ---------------- Files ---------------- */

function showFilesError(err = "") {
    const msg = String(err || "").trim();
    el("files-error").textContent = msg;
    el("files-error").classList.toggle("hidden", !msg);
}

function renderFilesTable(rows) {
    const sortedRows = sortByUpdatedAtDesc(rows);
    const html = `
    <table>
      <thead>
        <tr><th>path</th><th>size</th><th>updated_at</th><th></th></tr>
      </thead>
      <tbody>
        ${sortedRows.map((r) => `
          <tr>
            <td>${escapeHtml(r.path ?? "")}</td>
            <td>${escapeHtml(String(r.size ?? ""))}</td>
            <td>${renderUpdatedAtCell(r.updated_at)}</td>
            <td class="actions">
              <button type="button" data-act="del" data-path="${escapeAttr(r.path ?? "")}">Delete</button>
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
    el("files-table").innerHTML = html;

    el("files-table").querySelectorAll("button[data-act='del']").forEach((b) => {
        b.addEventListener("click", async () => {
            const path = b.getAttribute("data-path");
            await deleteFile(path);
        });
    });
}

async function refreshFiles() {
    showFilesError("");
    const rows = await apiJson(`${API}/files`);
    renderFilesTable(rows);
}

async function uploadFiles() {
    showFilesError("");
    const input = el("files-input");
    const files = Array.from(input.files || []);
    if (!files.length) {
        showFilesError("Select at least one file");
        return;
    }

    for (const file of files) {
        const fd = new FormData();
        fd.append("file", file, file.name);
        await apiJson(`${API}/file`, { method: "POST", body: fd });
    }

    input.value = "";
    await refreshFiles();
}

async function deleteFile(path) {
    showFilesError("");
    await apiJson(`${API}/file/${encodeURIComponent(path)}`, { method: "DELETE" });
    await refreshFiles();
}

/* ---------------- Utils + boot ---------------- */

function escapeHtml(s) {
    return String(s)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function escapeAttr(s) {
    return escapeHtml(s).replaceAll("\n", "");
}

function boot() {
    el("tab-builds").addEventListener("click", () => setTab("builds"));
    el("tab-lists").addEventListener("click", () => setTab("lists"));
    el("tab-profiles").addEventListener("click", () => setTab("profiles"));
    el("tab-files").addEventListener("click", () => setTab("files"));

    el("builds-refresh").addEventListener("click", () => refreshBuilds().catch((e) => showBuildsError(e.message || e)));
    el("builds-create").addEventListener("click", () => createBuild().catch((e) => showBuildsError(e.message || e)));

    el("lists-refresh").addEventListener("click", () => refreshLists().catch(() => { }));
    el("lists-create").addEventListener("click", () => openListEditor(null).catch(() => { }));

    el("profiles-refresh").addEventListener("click", () => refreshProfiles().catch(() => { }));
    el("profiles-create").addEventListener("click", () => openProfileEditor(null).catch(() => { }));
    el("files-refresh").addEventListener("click", () => refreshFiles().catch((e) => showFilesError(e.message || e)));
    el("files-upload").addEventListener("click", () => uploadFiles().catch((e) => showFilesError(e.message || e)));

    setTab("builds");
    refreshBuilds().catch((e) => showBuildsError(e.message || e));
    refreshLists().catch(() => { });
    refreshProfiles().catch(() => { });
    refreshFiles().catch((e) => showFilesError(e.message || e));
}

boot();
