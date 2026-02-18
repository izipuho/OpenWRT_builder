const API = "http://10.8.25.110:8080/api/v1";

const el = (id) => document.getElementById(id);

function setTab(tab) {
    const isLists = tab === "lists";
    el("tab-lists").classList.toggle("active", isLists);
    el("tab-profiles").classList.toggle("active", !isLists);
    el("view-lists").classList.toggle("hidden", !isLists);
    el("view-profiles").classList.toggle("hidden", isLists);
}

async function apiJson(path, opts = {}) {
    const headers = { ...(opts.headers || {}) };
    if (opts.body && !headers["Content-Type"]) {
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

function renderListsTable(rows) {
    const html = `
    <table>
      <thead>
        <tr><th>id</th><th>name</th><th>updated_at</th><th></th></tr>
      </thead>
      <tbody>
        ${rows.map((r) => `
          <tr>
            <td>${escapeHtml(r.id)}</td>
            <td>${escapeHtml(r.name ?? "")}</td>
            <td>${escapeHtml(r.updated_at ?? "")}</td>
            <td class="actions">
              <button type="button" data-act="edit" data-id="${escapeAttr(r.id)}">Edit</button>
              <button type="button" data-act="del" data-id="${escapeAttr(r.id)}">Delete</button>
            </td>
          </tr>
        `).join("")}
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

function listEditorHtml(id, name, content) {
    return `
    <h2>${id ? "Edit list" : "Create list"}</h2>
    ${id ? `
      <div class="row"><label>id</label><input id="list-id" value="${escapeAttr(id)}" disabled /></div>
    ` : `
      <div class="row"><label>id (optional)</label><input id="list-id" placeholder="slug" /></div>
    `}
    <div class="row"><label>name</label><input id="list-name" value="${escapeAttr(name)}" /></div>
    <div class="row"><label>content</label><textarea id="list-content" rows="12">${escapeHtml(content)}</textarea></div>
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
        showListsEditor(listEditorHtml(obj.id, obj.name ?? "", obj.content ?? ""));
        wireListEditor(obj.id);
    } else {
        showListsEditor(listEditorHtml("", "", ""));
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
            const content = el("list-content").value;

            if (existingId) {
                await apiJson(`${API}/list/${encodeURIComponent(existingId)}`, {
                    method: "PUT",
                    body: JSON.stringify({ name, content }),
                });
            } else {
                await apiJson(`${API}/list`, {
                    method: "POST",
                    body: JSON.stringify({ id: id || undefined, name, content }),
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

function defaultProfileJson() {
    return JSON.stringify(
        {
            name: "New profile",
            schema_version: 1,
            updated_at: new Date().toISOString(),
            profile: { lists: [], extra_include: [], extra_exclude: [] },
        },
        null,
        2
    );
}

function profileEditorHtml(id, jsonText) {
    return `
    <h2>${id ? "Edit profile (full replace)" : "Create profile"}</h2>
    ${id ? `
      <div class="row"><label>id</label><input id="profile-id" value="${escapeAttr(id)}" disabled /></div>
    ` : `
      <div class="row"><label>profile_id (optional)</label><input id="profile-id" placeholder="slug" /></div>
    `}
    <div class="row"><label>json</label><textarea id="profile-json" rows="16">${escapeHtml(jsonText)}</textarea></div>
    <div class="row buttons">
      <button id="profile-save" type="button">Save</button>
      <button id="profile-cancel" type="button">Cancel</button>
    </div>
    <pre id="profile-error" class="error hidden"></pre>
  `;
}

async function openProfileEditor(id = null) {
    if (id) {
        const obj = await apiJson(`${API}/profile/${encodeURIComponent(id)}`);
        showProfilesEditor(profileEditorHtml(id, JSON.stringify(obj, null, 2)));
        wireProfileEditor(id);
    } else {
        showProfilesEditor(profileEditorHtml("", defaultProfileJson()));
        wireProfileEditor(null);
    }
}

function wireProfileEditor(existingId) {
    el("profile-cancel").addEventListener("click", hideProfilesEditor);

    el("profile-save").addEventListener("click", async () => {
        try {
            el("profile-error").classList.add("hidden");
            const id = el("profile-id").value.trim();
            const txt = el("profile-json").value;
            const body = JSON.parse(txt);

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

    el("lists-refresh").addEventListener("click", () => refreshLists().catch(() => { }));
    el("lists-create").addEventListener("click", () => openListEditor(null).catch(() => { }));

    el("profiles-refresh").addEventListener("click", () => refreshProfiles().catch(() => { }));
    el("profiles-create").addEventListener("click", () => openProfileEditor(null).catch(() => { }));

    setTab("lists");
    refreshLists().catch(() => { });
    refreshProfiles().catch(() => { });
}

boot();
