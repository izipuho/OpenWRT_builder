const API = "http://10.8.25.110:8080/api/v1";
const API_BASE = API.replace(/\/api\/v1\/?$/, "");

const el = (id) => document.getElementById(id);

function setTab(tab) {
    ["lists", "profiles", "files"].forEach((name) => {
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

let listTemplateCache = null;

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

async function getListTemplate() {
    if (listTemplateCache) return listTemplateCache;
    try {
        const res = await fetch(`${API_BASE}/examples/list.json`);
        if (!res.ok) throw new Error(`template_http_${res.status}`);
        listTemplateCache = normalizeListTemplate(await res.json());
    } catch (_) {
        listTemplateCache = normalizeListTemplate({
            name: "New list",
            schema_version: 1,
            list: { include: [], exclude: [] },
        });
    }
    return listTemplateCache;
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

function renderListsTable(rows) {
    const html = `
    <table>
      <thead>
        <tr><th>id</th><th>name</th><th>updated_at</th><th></th></tr>
      </thead>
      <tbody>
        ${rows.map((r) => {
        const id = r.list_id ?? r.id ?? "";
        return `
          <tr>
            <td>${escapeHtml(id)}</td>
            <td>${escapeHtml(r.name ?? "")}</td>
            <td>${escapeHtml(r.updated_at ?? "")}</td>
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

function wireListEditor(existingId) {
    el("list-cancel").addEventListener("click", hideListsEditor);

    el("list-save").addEventListener("click", async () => {
        try {
            el("list-error").classList.add("hidden");
            const id = el("list-id").value.trim();
            const name = el("list-name").value.trim();
            const schemaVersion = Number(el("list-schema-version").value) || 1;
            const include = linesToArray(el("list-include").value);
            const exclude = linesToArray(el("list-exclude").value);
            const body = {
                name,
                schema_version: schemaVersion,
                list: {
                    include,
                    exclude,
                },
            };

            if (existingId) {
                await apiJson(`${API}/list/${encodeURIComponent(existingId)}`, {
                    method: "PUT",
                    body: JSON.stringify(body),
                });
            } else {
                await apiJson(`${API}/list`, {
                    method: "POST",
                    body: JSON.stringify({ list_id: id || undefined, ...body }),
                });
            }

            hideListsEditor();
            await refreshLists();
        } catch (e) {
            el("list-error").textContent = String(e.message || e);
            el("list-error").classList.remove("hidden");
        }
    });
}

async function deleteList(id) {
    await apiJson(`${API}/list/${encodeURIComponent(id)}`, { method: "DELETE" });
    await refreshLists();
}

/* ---------------- Profiles ---------------- */

let profileTemplateCache = null;

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
    if (profileTemplateCache) return profileTemplateCache;
    try {
        const res = await fetch(`${API_BASE}/examples/profile.json`);
        if (!res.ok) throw new Error(`template_http_${res.status}`);
        profileTemplateCache = normalizeProfileTemplate(await res.json());
    } catch (_) {
        profileTemplateCache = normalizeProfileTemplate({
            name: "New profile",
            schema_version: 1,
            profile: { lists: [], extra_include: [], extra_exclude: [], files: [] },
        });
    }
    return profileTemplateCache;
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
    const html = `
    <table>
      <thead>
        <tr><th>id</th><th>name</th><th>schema_version</th><th>updated_at</th><th></th></tr>
      </thead>
      <tbody>
        ${rows.map((r) => {
        const id = r.profile_id ?? r.id ?? "";
        return `
            <tr>
              <td>${escapeHtml(id)}</td>
              <td>${escapeHtml(r.name ?? "")}</td>
              <td>${escapeHtml(String(r.schema_version ?? ""))}</td>
              <td>${escapeHtml(r.updated_at ?? "")}</td>
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
    <div class="row"><label>files</label>${checklistHtml("profile-files", mergedFileOptions, selectedFiles, "No files uploaded")}</div>
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
    el("profile-cancel").addEventListener("click", hideProfilesEditor);

    el("profile-save").addEventListener("click", async () => {
        try {
            el("profile-error").classList.add("hidden");
            const id = el("profile-id").value.trim();
            const name = el("profile-name").value.trim();
            const schemaVersion = Number(el("profile-schema-version").value) || 1;
            const lists = checkedValues("profile-lists");
            const include = linesToArray(el("profile-include").value);
            const exclude = linesToArray(el("profile-exclude").value);
            const files = checkedValues("profile-files");
            const body = {
                name,
                schema_version: schemaVersion,
                profile: {
                    lists,
                    extra_include: include,
                    extra_exclude: exclude,
                    files,
                },
            };

            if (existingId) {
                await apiJson(`${API}/profile/${encodeURIComponent(existingId)}`, {
                    method: "PUT",
                    body: JSON.stringify(body),
                });
            } else {
                await apiJson(`${API}/profile`, {
                    method: "POST",
                    body: JSON.stringify({ profile_id: id || undefined, ...body }),
                });
            }

            hideProfilesEditor();
            await refreshProfiles();
        } catch (e) {
            el("profile-error").textContent = String(e.message || e);
            el("profile-error").classList.remove("hidden");
        }
    });
}

async function deleteProfile(id) {
    await apiJson(`${API}/profile/${encodeURIComponent(id)}`, { method: "DELETE" });
    await refreshProfiles();
}

/* ---------------- Files ---------------- */

function showFilesError(err = "") {
    const msg = String(err || "").trim();
    el("files-error").textContent = msg;
    el("files-error").classList.toggle("hidden", !msg);
}

function renderFilesTable(rows) {
    const html = `
    <table>
      <thead>
        <tr><th>path</th><th>size</th><th>updated_at</th><th></th></tr>
      </thead>
      <tbody>
        ${rows.map((r) => `
          <tr>
            <td>${escapeHtml(r.path ?? "")}</td>
            <td>${escapeHtml(String(r.size ?? ""))}</td>
            <td>${escapeHtml(r.updated_at ?? "")}</td>
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
    el("tab-lists").addEventListener("click", () => setTab("lists"));
    el("tab-profiles").addEventListener("click", () => setTab("profiles"));
    el("tab-files").addEventListener("click", () => setTab("files"));

    el("lists-refresh").addEventListener("click", () => refreshLists().catch(() => { }));
    el("lists-create").addEventListener("click", () => openListEditor(null).catch(() => { }));

    el("profiles-refresh").addEventListener("click", () => refreshProfiles().catch(() => { }));
    el("profiles-create").addEventListener("click", () => openProfileEditor(null).catch(() => { }));
    el("files-refresh").addEventListener("click", () => refreshFiles().catch((e) => showFilesError(e.message || e)));
    el("files-upload").addEventListener("click", () => uploadFiles().catch((e) => showFilesError(e.message || e)));

    setTab("lists");
    refreshLists().catch(() => { });
    refreshProfiles().catch(() => { });
    refreshFiles().catch((e) => showFilesError(e.message || e));
}

boot();
