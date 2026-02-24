const BACKEND_ADDRESS_STORAGE_KEY = "openwrt_builder_backend_address";
const API_PATH_STORAGE_KEY = "openwrt_builder_api_path";
const LEGACY_API_BASE_STORAGE_KEY = "openwrt_builder_api_base";
const DEFAULT_BACKEND_ADDRESS = "";
const DEFAULT_API_PATH = "api/v1";
const TAB_NAMES = ["builds", "lists", "profiles", "files", "settings"];
let API = DEFAULT_API_PATH;
const BUILDS_AUTO_REFRESH_MS = 2000;
let buildsAutoRefreshHandle = null;
const rowSelection = {
    lists: new Set(),
    profiles: new Set(),
    builds: new Set(),
};
const entitySort = {
    lists: { field: "updated", direction: "desc" },
    profiles: { field: "updated", direction: "desc" },
};
const entitySearch = {
    lists: "",
    profiles: "",
};
const entityRowsCache = {
    lists: [],
    profiles: [],
};

const templateCache = {
    list: null,
    profile: null,
};
const fileTargetDrafts = new Map();

const el = (id) => document.getElementById(id);

function normalizeBackendAddress(input) {
    const value = String(input || "").trim();
    if (!value) return DEFAULT_BACKEND_ADDRESS;
    return value.replace(/\/+$/, "");
}

function normalizeApiPath(input) {
    const value = String(input || "").trim();
    if (!value) return DEFAULT_API_PATH;
    return value.replace(/^\/+/, "").replace(/\/+$/, "");
}

function buildApiBase(address, path) {
    const safeAddress = normalizeBackendAddress(address);
    const safePath = normalizeApiPath(path);
    return safeAddress ? `${safeAddress}/${safePath}` : safePath;
}

function buildExamplesBase(address) {
    const safeAddress = normalizeBackendAddress(address);
    return safeAddress ? `${safeAddress}/examples` : "examples";
}

function parseLegacyApiBase(input) {
    const raw = String(input || "").trim().replace(/\/+$/, "");
    if (!raw) return null;

    let match = raw.match(/^(https?:\/\/[^/]+)\/(.+)$/i);
    if (match) return { address: normalizeBackendAddress(match[1]), path: normalizeApiPath(match[2]) };

    match = raw.match(/^\/?(.+)$/i);
    if (match) return { address: DEFAULT_BACKEND_ADDRESS, path: normalizeApiPath(match[1]) };

    return null;
}

function loadApiConfigFromStorage() {
    try {
        const addressStored = window.localStorage.getItem(BACKEND_ADDRESS_STORAGE_KEY);
        const pathStored = window.localStorage.getItem(API_PATH_STORAGE_KEY);
        if (addressStored !== null || pathStored !== null) {
            return {
                address: normalizeBackendAddress(addressStored),
                path: normalizeApiPath(pathStored),
            };
        }

        const legacy = window.localStorage.getItem(LEGACY_API_BASE_STORAGE_KEY);
        const parsed = parseLegacyApiBase(legacy);
        if (parsed) return parsed;
        return { address: DEFAULT_BACKEND_ADDRESS, path: DEFAULT_API_PATH };
    } catch (_) {
        return { address: DEFAULT_BACKEND_ADDRESS, path: DEFAULT_API_PATH };
    }
}

function saveApiConfigToStorage(address, path) {
    try {
        window.localStorage.setItem(BACKEND_ADDRESS_STORAGE_KEY, normalizeBackendAddress(address));
        window.localStorage.setItem(API_PATH_STORAGE_KEY, normalizeApiPath(path));
    } catch (_) {
        // Ignore storage errors (private mode, quota, blocked storage).
    }
}

function refreshAllViews() {
    refreshBuilds().catch((e) => showBuildsError(e.message || e));
    refreshLists().catch((e) => showListsError(e.message || e));
    refreshProfiles().catch((e) => showProfilesError(e.message || e));
    refreshFiles().catch((e) => showFilesError(e.message || e));
}

function renderApiBaseState() {
    const addressInput = el("api-backend-address");
    const pathInput = el("api-path");
    const state = el("api-base-state");
    if (!addressInput || !pathInput || !state) return;

    const address = normalizeBackendAddress(addressInput.value);
    const path = normalizeApiPath(pathInput.value);
    const mode = address ? "remote backend server" : "same-origin backend";
    const apiBase = buildApiBase(address, path);
    const examplesBase = buildExamplesBase(address);
    state.textContent = `Active API: ${apiBase} | examples: ${examplesBase} (${mode})`;
}

function applyApiConfig(nextAddressRaw, nextPathRaw) {
    const address = normalizeBackendAddress(nextAddressRaw);
    const path = normalizeApiPath(nextPathRaw);
    API = buildApiBase(address, path);
    saveApiConfigToStorage(address, path);
    templateCache.list = null;
    templateCache.profile = null;

    const addressInput = el("api-backend-address");
    const pathInput = el("api-path");
    if (addressInput) addressInput.value = address;
    if (pathInput) pathInput.value = path;

    renderApiBaseState();
    refreshAllViews();
}

function wireApiBaseControls() {
    const addressInput = el("api-backend-address");
    const pathInput = el("api-path");
    const applyBtn = el("api-base-apply");
    const resetBtn = el("api-base-reset");
    if (!addressInput || !pathInput || !applyBtn || !resetBtn) return;

    const submit = () => applyApiConfig(addressInput.value, pathInput.value);
    applyBtn.addEventListener("click", submit);
    resetBtn.addEventListener("click", () => applyApiConfig(DEFAULT_BACKEND_ADDRESS, DEFAULT_API_PATH));
    addressInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            submit();
        }
    });
    pathInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            submit();
        }
    });
    renderApiBaseState();
}

function setTab(tab) {
    TAB_NAMES.forEach((name) => {
        const active = tab === name;
        const tabEl = el(`tab-${name}`);
        const viewEl = el(`view-${name}`);
        tabEl.classList.toggle("active", active);
        tabEl.setAttribute("aria-selected", String(active));
        tabEl.setAttribute("tabindex", active ? "0" : "-1");
        viewEl.classList.toggle("hidden", !active);
        viewEl.setAttribute("aria-hidden", String(!active));
    });
}

function wireTabKeyboardNavigation() {
    TAB_NAMES.forEach((name, idx) => {
        const tabEl = el(`tab-${name}`);
        tabEl.addEventListener("keydown", (event) => {
            let nextIdx = idx;
            if (event.key === "ArrowRight") nextIdx = (idx + 1) % TAB_NAMES.length;
            else if (event.key === "ArrowLeft") nextIdx = (idx - 1 + TAB_NAMES.length) % TAB_NAMES.length;
            else if (event.key === "Home") nextIdx = 0;
            else if (event.key === "End") nextIdx = TAB_NAMES.length - 1;
            else return;

            event.preventDefault();
            const nextName = TAB_NAMES[nextIdx];
            setTab(nextName);
            el(`tab-${nextName}`).focus();
        });
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
        const rel = String(examplePath || "").replace(/^\/+/, "");
        const addressInput = el("api-backend-address");
        const examplesBase = buildExamplesBase(addressInput?.value || "");
        const res = await fetch(`${examplesBase}/${rel}`);
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
        examplePath: "list.json",
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

function entityRowId(scope, row) {
    if (scope === "lists") return String(row?.list_id ?? row?.id ?? "").trim();
    if (scope === "profiles") return String(row?.profile_id ?? row?.id ?? "").trim();
    return String(row?.id ?? "").trim();
}

function sortEntityRows(scope, rows) {
    const state = entitySort[scope] || { field: "updated", direction: "desc" };
    const dir = state.direction === "asc" ? 1 : -1;
    return [...(rows || [])].sort((a, b) => {
        if (state.field === "name") {
            const aName = String(a?.name || "").trim();
            const bName = String(b?.name || "").trim();
            const byName = aName.localeCompare(bName, undefined, { sensitivity: "base" }) * dir;
            if (byName !== 0) return byName;
            return entityRowId(scope, a).localeCompare(entityRowId(scope, b), undefined, { sensitivity: "base" }) * dir;
        }

        const aTs = timestampToMs(a?.updated_at);
        const bTs = timestampToMs(b?.updated_at);
        if (!Number.isNaN(aTs) && !Number.isNaN(bTs)) return (aTs - bTs) * dir;
        if (!Number.isNaN(aTs)) return -1 * dir;
        if (!Number.isNaN(bTs)) return 1 * dir;
        const aRaw = String(a?.updated_at || "");
        const bRaw = String(b?.updated_at || "");
        const byUpdatedRaw = aRaw.localeCompare(bRaw, undefined, { sensitivity: "base" }) * dir;
        if (byUpdatedRaw !== 0) return byUpdatedRaw;
        return entityRowId(scope, a).localeCompare(entityRowId(scope, b), undefined, { sensitivity: "base" }) * dir;
    });
}

function renderEntitySortButtons(scope) {
    const state = entitySort[scope];
    if (!state) return;
    const nameBtn = el(`${scope}-sort-name`);
    const updatedBtn = el(`${scope}-sort-updated`);
    if (!nameBtn || !updatedBtn) return;

    const nameActive = state.field === "name";
    const updatedActive = state.field === "updated";
    const dirLabel = state.direction === "asc" ? "ascending" : "descending";
    nameBtn.setAttribute("title", `Sort by name${nameActive ? ` (${dirLabel})` : ""}`);
    nameBtn.setAttribute("aria-label", `Sort by name${nameActive ? ` (${dirLabel})` : ""}`);
    updatedBtn.setAttribute("title", `Sort by updated${updatedActive ? ` (${dirLabel})` : ""}`);
    updatedBtn.setAttribute("aria-label", `Sort by updated${updatedActive ? ` (${dirLabel})` : ""}`);
    nameBtn.setAttribute("data-dir", nameActive ? state.direction : "");
    updatedBtn.setAttribute("data-dir", updatedActive ? state.direction : "");
    nameBtn.classList.toggle("active", nameActive);
    updatedBtn.classList.toggle("active", updatedActive);
}

function setEntitySort(scope, field) {
    const state = entitySort[scope];
    if (!state) return;
    if (state.field === field) {
        state.direction = state.direction === "asc" ? "desc" : "asc";
    } else {
        state.field = field;
        state.direction = field === "name" ? "asc" : "desc";
    }
    renderEntitySortButtons(scope);
}

function filterEntityRows(scope, rows) {
    const query = String(entitySearch[scope] || "").trim().toLowerCase();
    if (!query) return [...(rows || [])];
    return [...(rows || [])].filter((row) => {
        const id = entityRowId(scope, row).toLowerCase();
        const name = String(row?.name || "").trim().toLowerCase();
        return id.includes(query) || name.includes(query);
    });
}

function syncRowSelection(scope, ids) {
    if (!rowSelection[scope]) return;
    const currentIds = new Set((ids || []).map((id) => String(id || "").trim()).filter(Boolean));
    rowSelection[scope] = new Set(Array.from(rowSelection[scope]).filter((id) => currentIds.has(id)));
}

function wireTableRowSelection(containerId, scope) {
    const container = el(containerId);
    container.querySelectorAll(`input[data-select-scope="${scope}"][data-id]`).forEach((input) => {
        input.addEventListener("change", () => {
            const id = String(input.getAttribute("data-id") || "").trim();
            if (!id) return;
            if (input.checked) rowSelection[scope].add(id);
            else rowSelection[scope].delete(id);
        });
    });
}

function wireCardRowToggle(containerId, scope) {
    const container = el(containerId);
    container.querySelectorAll(`.entity-card[data-select-scope="${scope}"][data-id]`).forEach((card) => {
        card.addEventListener("click", (event) => {
            if (event.target.closest("button")) return;
            const input = card.querySelector(`input[data-select-scope="${scope}"][data-id]`);
            if (!input || input.disabled) return;
            input.checked = !input.checked;
            input.dispatchEvent(new Event("change"));
        });
    });
}

function setVisibleRowSelection(scope, checked) {
    const selected = Boolean(checked);
    document.querySelectorAll(`input[data-select-scope="${scope}"][data-id]`).forEach((input) => {
        if (input.disabled) return;
        const id = String(input.getAttribute("data-id") || "").trim();
        if (!id) return;
        input.checked = selected;
        if (selected) rowSelection[scope].add(id);
        else rowSelection[scope].delete(id);
    });
}

async function deleteSelectedItems({
    scope,
    errorSetter,
    deleteOne,
    successRefresh,
    entityLabel,
}) {
    const ids = Array.from(rowSelection[scope] || []);
    if (!ids.length) {
        errorSetter(`No ${entityLabel} selected`);
        return;
    }

    errorSetter("");
    const errors = [];
    for (const id of ids) {
        try {
            await deleteOne(id);
            rowSelection[scope].delete(id);
        } catch (e) {
            errors.push(`${id}: ${String(e.message || e)}`);
        }
    }

    await successRefresh();
    if (errors.length) {
        errorSetter(`Deleted ${ids.length - errors.length}/${ids.length} ${entityLabel}\n${errors.join("\n")}`);
        return;
    }
    errorSetter(`Deleted ${ids.length} ${entityLabel}`);
}

function renderListsTable(rows) {
    if (Array.isArray(rows)) entityRowsCache.lists = rows;
    const sortedRows = sortEntityRows("lists", entityRowsCache.lists);
    const visibleRows = filterEntityRows("lists", sortedRows);
    const ids = visibleRows.map((r) => r.list_id ?? r.id ?? "");
    syncRowSelection("lists", ids);
    const html = !visibleRows.length
        ? `<div class="muted">${sortedRows.length ? "No matches" : "No lists yet"}</div>`
        : `
    <div class="entity-cards-grid">
      ${visibleRows.map((r) => {
            const id = r.list_id ?? r.id ?? "";
            return `
        <article class="entity-card" data-select-scope="lists" data-id="${escapeAttr(id)}">
          <input type="checkbox" data-select-scope="lists" data-id="${escapeAttr(id)}" ${rowSelection.lists.has(String(id)) ? "checked" : ""} />
          <div class="entity-card-main">
            <div class="entity-card-title">${escapeHtml(r.name ?? "") || "<span class=\"muted\">Unnamed list</span>"}</div>
            <div class="entity-card-id">${escapeHtml(id)}</div>
          </div>
          <div class="entity-card-meta"><span class="muted">upd.</span> ${renderUpdatedAtCell(r.updated_at) || "<span class=\"muted\">-</span>"}</div>
          <div class="entity-card-actions">
            <button type="button" class="icon-btn icon-edit" data-act="edit" data-id="${escapeAttr(id)}" title="Edit list" aria-label="Edit list"></button>
            <button type="button" class="icon-btn icon-delete" data-act="del" data-id="${escapeAttr(id)}" title="Delete list" aria-label="Delete list"></button>
          </div>
        </article>
      `;
        }).join("")}
    </div>
  `;
    el("lists-table").innerHTML = html;
    wireTableRowSelection("lists-table", "lists");
    wireCardRowToggle("lists-table", "lists");
    renderEntitySortButtons("lists");

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

function showListsError(err = "") {
    const msg = String(err || "").trim();
    el("lists-error").textContent = msg;
    el("lists-error").classList.toggle("hidden", !msg);
}

async function importLists() {
    showListsError("");
    const payload = await apiJson(`${API}/lists/import`, { method: "POST" });
    const found = Number(payload?.found) || 0;
    const created = Number(payload?.created) || 0;
    const skipped = Number(payload?.skipped) || 0;
    const errors = Number(payload?.errors) || 0;
    showListsError(`import: found=${found}, created=${created}, skipped=${skipped}, errors=${errors}`);
    await refreshLists();
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
        examplePath: "profile.json",
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
        .filter(Boolean)
        .sort((a, b) => {
            const byTitle = a.title.localeCompare(b.title, undefined, { sensitivity: "base" });
            if (byTitle !== 0) return byTitle;
            return a.id.localeCompare(b.id, undefined, { sensitivity: "base" });
        });
}

async function getFileChoices() {
    const rows = await apiJson(`${API}/files`);
    return rows
        .map((r) => {
            const sourcePath = String(r.source_path || r.path || "").trim();
            const targetPath = String(r.target_path || sourcePath).trim();
            if (!sourcePath || !targetPath) return null;
            const targetPathUi = toUiRootfsDir(targetPath);
            return {
                id: sourcePath,
                sourcePath,
                targetPath,
                title: sourcePath === targetPath ? sourcePath : `${sourcePath} -> ${targetPathUi}`,
                meta: typeof r.size === "number" ? `${r.size} bytes` : sourcePath,
            };
        })
        .filter(Boolean);
}

function checkedValues(group) {
    return Array.from(document.querySelectorAll(`input[data-group="${group}"]:checked`))
        .map((elx) => elx.value);
}

function wireChecklistBulkActions(root = document) {
    root.querySelectorAll("button[data-checklist-action][data-group]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const group = String(btn.getAttribute("data-group") || "").trim();
            const action = String(btn.getAttribute("data-checklist-action") || "").trim();
            if (!group) return;
            const checked = action === "select-all";
            document.querySelectorAll(`input[data-group="${group}"]`).forEach((input) => {
                input.checked = checked;
            });
        });
    });
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
    if (Array.isArray(rows)) entityRowsCache.profiles = rows;
    const sortedRows = sortEntityRows("profiles", entityRowsCache.profiles);
    const visibleRows = filterEntityRows("profiles", sortedRows);
    const ids = visibleRows.map((r) => r.profile_id ?? r.id ?? "");
    syncRowSelection("profiles", ids);
    const html = !visibleRows.length
        ? `<div class="muted">${sortedRows.length ? "No matches" : "No profiles yet"}</div>`
        : `
    <div class="entity-cards-grid">
      ${visibleRows.map((r) => {
            const id = r.profile_id ?? r.id ?? "";
            return `
        <article class="entity-card" data-select-scope="profiles" data-id="${escapeAttr(id)}">
          <input type="checkbox" data-select-scope="profiles" data-id="${escapeAttr(id)}" ${rowSelection.profiles.has(String(id)) ? "checked" : ""} />
          <div class="entity-card-main">
            <div class="entity-card-title">${escapeHtml(r.name ?? "") || "<span class=\"muted\">Unnamed profile</span>"}</div>
            <div class="entity-card-id">${escapeHtml(id)}</div>
          </div>
          <div class="entity-card-meta"><span class="muted">upd.</span> ${renderUpdatedAtCell(r.updated_at) || "<span class=\"muted\">-</span>"}</div>
          <div class="entity-card-actions">
            <button type="button" class="icon-btn icon-edit" data-act="edit" data-id="${escapeAttr(id)}" title="Edit profile" aria-label="Edit profile"></button>
            <button type="button" class="icon-btn icon-delete" data-act="del" data-id="${escapeAttr(id)}" title="Delete profile" aria-label="Delete profile"></button>
          </div>
        </article>
      `;
        }).join("")}
    </div>
  `;
    el("profiles-table").innerHTML = html;
    wireTableRowSelection("profiles-table", "profiles");
    wireCardRowToggle("profiles-table", "profiles");
    renderEntitySortButtons("profiles");

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
    showProfilesError("");
    const rows = await apiJson(`${API}/profiles`);
    renderProfilesTable(rows);
}

function showProfilesError(err = "") {
    const msg = String(err || "").trim();
    el("profiles-error").textContent = msg;
    el("profiles-error").classList.toggle("hidden", !msg);
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
    const availableFileIds = new Set(normalizedFileOptions.map((o) => o.id));
    const selectedExistingFiles = selectedFiles.filter((v) => availableFileIds.has(v));
    const defaultSelectedFiles = !id && selectedFiles.length === 0
        ? normalizedFileOptions.map((o) => o.id)
        : selectedExistingFiles;

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
    <div class="row">
      <label>files</label>
      <div class="row buttons">
        <button type="button" data-checklist-action="select-all" data-group="profile-files">Select all</button>
        <button type="button" data-checklist-action="deselect-all" data-group="profile-files">Deselect all</button>
      </div>
      ${checklistHtml("profile-files", normalizedFileOptions, defaultSelectedFiles, "No files uploaded")}
    </div>
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
        wireChecklistBulkActions(el("profiles-editor"));
    } else {
        const model = await getProfileTemplate();
        showProfilesEditor(profileEditorHtml("", model, listOptions, fileOptions));
        wireProfileEditor(null);
        wireChecklistBulkActions(el("profiles-editor"));
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

function renderBuildStateBadge(rawState) {
    const state = String(rawState || "").trim().toLowerCase();
    const known = new Set(["queued", "running", "done", "failed", "canceled"]);
    const normalized = known.has(state) ? state : "unknown";
    const label = state || "unknown";
    return `<span class="state-badge state-${escapeAttr(normalized)}">${escapeHtml(label)}</span>`;
}

async function copyText(text) {
    const value = String(text ?? "");
    if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
        return;
    }
    const node = document.createElement("textarea");
    node.value = value;
    node.setAttribute("readonly", "");
    node.style.position = "absolute";
    node.style.left = "-9999px";
    document.body.appendChild(node);
    node.select();
    document.execCommand("copy");
    document.body.removeChild(node);
}

function hideBuildRequestDetails() {
    const tooltip = el("builds-request-tooltip");
    tooltip.classList.add("hidden");
    tooltip.style.left = "";
    tooltip.style.top = "";
    tooltip.dataset.buildId = "";
    tooltip.dataset.requestJson = "";
    el("builds-request-tooltip-body").textContent = "";
}

function hideBuildMessageDetails() {
    const tooltip = el("builds-message-tooltip");
    tooltip.classList.add("hidden");
    tooltip.style.left = "";
    tooltip.style.top = "";
    tooltip.dataset.buildId = "";
    tooltip.dataset.messageText = "";
    el("builds-message-tooltip-body").textContent = "";
}

function hideBuildTooltips() {
    hideBuildRequestDetails();
    hideBuildMessageDetails();
}

function positionTooltip(tooltip, anchorEl) {
    if (!anchorEl) return;
    const rect = anchorEl.getBoundingClientRect();
    const minGap = 8;
    tooltip.style.left = `${window.scrollX + minGap}px`;
    tooltip.style.top = `${window.scrollY + minGap}px`;

    const tipRect = tooltip.getBoundingClientRect();
    let left = window.scrollX + rect.left;
    let top = window.scrollY + rect.bottom + minGap;

    const maxLeft = window.scrollX + window.innerWidth - tipRect.width - minGap;
    if (left > maxLeft) left = maxLeft;
    if (left < window.scrollX + minGap) left = window.scrollX + minGap;

    const maxTop = window.scrollY + window.innerHeight - tipRect.height - minGap;
    if (top > maxTop) {
        top = window.scrollY + rect.top - tipRect.height - minGap;
    }
    if (top < window.scrollY + minGap) top = window.scrollY + minGap;

    tooltip.style.left = `${Math.round(left)}px`;
    tooltip.style.top = `${Math.round(top)}px`;
}

function showBuildRequestDetails(build, anchorEl) {
    const buildId = String(build?.build_id || "").trim();
    const request = build?.request ?? {};
    const requestJson = JSON.stringify(request, null, 2);
    el("builds-request-tooltip-title").textContent = buildId
        ? `Build request: ${buildId}`
        : "Build request";
    const tooltip = el("builds-request-tooltip");
    el("builds-request-tooltip-body").textContent = requestJson;
    tooltip.dataset.buildId = buildId;
    tooltip.dataset.requestJson = requestJson;
    tooltip.classList.remove("hidden");
    positionTooltip(tooltip, anchorEl);
}

function showBuildMessageDetails(buildId, messageText, anchorEl, titlePrefix = "Build message") {
    const tooltip = el("builds-message-tooltip");
    const fullText = String(messageText ?? "");
    el("builds-message-tooltip-title").textContent = buildId
        ? `${titlePrefix}: ${buildId}`
        : titlePrefix;
    el("builds-message-tooltip-body").textContent = fullText;
    tooltip.dataset.buildId = String(buildId || "");
    tooltip.dataset.messageText = fullText;
    tooltip.classList.remove("hidden");
    positionTooltip(tooltip, anchorEl);
}

function formatPhase(rawPhase) {
    const phase = String(rawPhase || "").trim();
    if (!phase) return "-";
    return phase.replaceAll("_", " ");
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

function renderBuildSimpleSelectOptions(selectId, values, {
    selectedValue = "",
    emptyLabel = "No options available",
} = {}) {
    const select = el(selectId);
    const normalized = (values || [])
        .map((v) => String(v || "").trim())
        .filter(Boolean);

    if (!normalized.length) {
        select.innerHTML = `<option value="">${escapeHtml(emptyLabel)}</option>`;
        return "";
    }

    const selected = normalized.includes(selectedValue) ? selectedValue : normalized[0];
    select.innerHTML = normalized
        .map((value) => `<option value="${escapeAttr(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(value)}</option>`)
        .join("");
    return selected;
}

async function fetchBuildTargets(version) {
    if (!version) return [];
    const payload = await apiJson(`${API}/build-targets?version=${encodeURIComponent(version)}`);
    return Array.isArray(payload?.targets) ? payload.targets : [];
}

async function fetchBuildSubtargets(version, target) {
    if (!version || !target) return [];
    const payload = await apiJson(
        `${API}/build-subtargets?version=${encodeURIComponent(version)}&target=${encodeURIComponent(target)}`
    );
    return Array.isArray(payload?.subtargets) ? payload.subtargets : [];
}

async function fetchBuildPlatforms(version, target, subtarget) {
    if (!version || !target || !subtarget) return [];
    const payload = await apiJson(
        `${API}/build-platforms?version=${encodeURIComponent(version)}&target=${encodeURIComponent(target)}&subtarget=${encodeURIComponent(subtarget)}`
    );
    return Array.isArray(payload?.platforms) ? payload.platforms : [];
}

async function syncBuildSelectors() {
    const version = String(el("builds-version").value || "").trim();
    const selectedTarget = String(el("builds-target").value || "").trim();
    const selectedSubtarget = String(el("builds-subtarget").value || "").trim();
    const selectedPlatform = String(el("builds-platform").value || "").trim();

    if (!version) {
        renderBuildSimpleSelectOptions("builds-target", [], { emptyLabel: "Select version first" });
        renderBuildSimpleSelectOptions("builds-subtarget", [], { emptyLabel: "Select target first" });
        renderBuildSimpleSelectOptions("builds-platform", [], { emptyLabel: "Select subtarget first" });
        return;
    }

    const targets = await fetchBuildTargets(version).catch(() => []);
    const target = renderBuildSimpleSelectOptions("builds-target", targets, {
        selectedValue: selectedTarget,
        emptyLabel: "No targets available",
    });
    if (!target) {
        renderBuildSimpleSelectOptions("builds-subtarget", [], { emptyLabel: "Select target first" });
        renderBuildSimpleSelectOptions("builds-platform", [], { emptyLabel: "Select subtarget first" });
        return;
    }

    const subtargets = await fetchBuildSubtargets(version, target).catch(() => []);
    const subtarget = renderBuildSimpleSelectOptions("builds-subtarget", subtargets, {
        selectedValue: selectedSubtarget,
        emptyLabel: "No subtargets available",
    });
    if (!subtarget) {
        renderBuildSimpleSelectOptions("builds-platform", [], { emptyLabel: "Select subtarget first" });
        return;
    }

    const platforms = await fetchBuildPlatforms(version, target, subtarget).catch(() => []);
    renderBuildSimpleSelectOptions("builds-platform", platforms, {
        selectedValue: selectedPlatform,
        emptyLabel: "No platforms available",
    });
}

function renderBuildsTable(rows) {
    const sortedRows = sortByUpdatedAtDesc(rows);
    const ids = sortedRows
        .filter((row) => String(row?.state || "") !== "running")
        .map((row) => row?.build_id || "");
    syncRowSelection("builds", ids);
    const byId = new Map(sortedRows.map((row) => [String(row?.build_id || ""), row]));
    const html = `
    <table>
      <thead>
        <tr><th></th><th>build_id</th><th>state</th><th>phase</th><th>progress</th><th>updated_at</th><th>message</th><th></th></tr>
      </thead>
      <tbody>
        ${sortedRows.map((r) => {
        const buildId = String(r.build_id || "");
        const state = String(r.state || "");
        const canStop = state === "running" && !r.cancel_requested;
        const canDelete = state !== "running";
        const canDownload = state === "done";
        const canRebuild = state !== "running";
        const fullMessage = String(r.message ?? "");
        return `
          <tr>
            <td class="select-cell">
              <input type="checkbox" data-select-scope="builds" data-id="${escapeAttr(buildId)}" ${canDelete ? "" : "disabled"} ${rowSelection.builds.has(String(buildId)) ? "checked" : ""} />
            </td>
            <td>${escapeHtml(buildId)}</td>
            <td>${renderBuildStateBadge(state)}</td>
            <td>${escapeHtml(formatPhase(r.phase))}</td>
            <td>${escapeHtml(String(r.progress ?? ""))}%</td>
            <td>${renderUpdatedAtCell(r.updated_at)}</td>
            <td>
              ${fullMessage
                ? `
                  <div class="message-cell">
                    <span class="message-text" title="${escapeAttr(fullMessage)}">${escapeHtml(fullMessage)}</span>
                    <button
                      type="button"
                      class="view-icon-btn view-icon-corner"
                      data-act="show-message"
                      data-id="${escapeAttr(buildId)}"
                      title="Show full message"
                      aria-label="Show full message"
                    ></button>
                  </div>
                `
                : `<span class="muted">-</span>`
            }
            </td>
            <td class="actions build-actions">
              <div class="actions-wrap">
                <button
                  type="button"
                  class="view-icon-btn view-icon-corner"
                  data-act="params"
                  data-id="${escapeAttr(buildId)}"
                  title="Show build params"
                  aria-label="Show build params"
                ></button>
                <div class="actions-buttons">
                  <button type="button" data-act="logs" data-id="${escapeAttr(buildId)}">Logs</button>
                  ${canStop ? `<button type="button" data-act="stop" data-id="${escapeAttr(buildId)}">Stop</button>` : ""}
                  ${canRebuild ? `<button type="button" data-act="rebuild" data-id="${escapeAttr(buildId)}">Rebuild</button>` : ""}
                  ${canDelete ? `<button type="button" data-act="delete" data-id="${escapeAttr(buildId)}">Delete</button>` : ""}
                  ${canDownload ? `<button type="button" data-act="download" data-id="${escapeAttr(buildId)}">Download</button>` : ""}
                </div>
              </div>
            </td>
          </tr>
        `;
    }).join("")}
      </tbody>
    </table>
  `;
    el("builds-table").innerHTML = html;
    wireTableRowSelection("builds-table", "builds");

    el("builds-table").querySelectorAll("button").forEach((b) => {
        b.addEventListener("click", async () => {
            const buildId = b.getAttribute("data-id");
            const act = b.getAttribute("data-act");
            if (act === "params") {
                await viewBuildRequest(buildId, b);
            } else if (act === "show-message") {
                const fullMessage = String(byId.get(String(buildId || ""))?.message ?? "");
                if (!fullMessage) return;
                await viewBuildMessage(buildId, fullMessage, b);
            } else if (act === "logs") {
                await viewBuildLogs(buildId, b);
            } else if (act === "stop") {
                await cancelBuild(buildId);
            } else if (act === "rebuild") {
                await rebuildBuild(buildId);
            } else if (act === "delete") {
                await deleteBuild(buildId);
            } else if (act === "download") {
                await downloadBuild(buildId);
            }
        });
    });
}

function selectedBuildOutputImages() {
    const allowed = new Set(["sysupgrade", "factory"]);
    return checkedValues("builds-images")
        .map((v) => String(v || "").trim())
        .filter((v, idx, arr) => allowed.has(v) && arr.indexOf(v) === idx);
}

function wireBuildImagesSelection() {
    const inputs = Array.from(document.querySelectorAll('input[data-group="builds-images"]'));
    if (!inputs.length) return;
    inputs.forEach((input) => {
        input.addEventListener("change", () => {
            const checked = inputs.filter((item) => item.checked);
            if (checked.length) return;
            const fallback = inputs.find((item) => item !== input) || input;
            fallback.checked = true;
        });
    });
}

async function downloadBuild(buildId) {
    showBuildsError("");
    const items = await apiJson(`${API}/build/${encodeURIComponent(buildId)}/artifacts`);
    if (!Array.isArray(items) || !items.length) {
        showBuildsError(`No artifacts for build ${buildId}`);
        return;
    }

    const preferred = items.find((item) => String(item?.role || "") === "primary") || items[0];
    let selected = preferred;
    if (items.length > 1) {
        const options = items.map((item) => String(item?.id || "").trim()).filter(Boolean);
        const pick = window.prompt(
            `Select artifact id to download (${options.join(", ")})`,
            String(preferred?.id || "")
        );
        if (pick === null) return;
        const picked = items.find((item) => String(item?.id || "").trim() === String(pick).trim());
        if (!picked) {
            showBuildsError(`Unknown artifact id: ${pick}`);
            return;
        }
        selected = picked;
    }

    const artifactId = String(selected?.id || "").trim();
    if (!artifactId) {
        showBuildsError(`Invalid artifact id for build ${buildId}`);
        return;
    }
    window.open(
        `${API}/build/${encodeURIComponent(buildId)}/download/${encodeURIComponent(artifactId)}`,
        "_blank"
    );
}

async function refreshBuilds() {
    showBuildsError("");
    const [profiles, builds, versionsPayload] = await Promise.all([
        apiJson(`${API}/profiles`),
        apiJson(`${API}/builds`),
        apiJson(`${API}/build-versions`).catch(() => ({ latest: [] })),
    ]);
    renderBuildProfileOptions(profiles);
    renderBuildVersionOptions(versionsPayload);
    await syncBuildSelectors();
    renderBuildsTable(builds);
}

function normalizeBuildRequest(request = {}) {
    const options = request?.options || {};
    const outputImages = Array.isArray(options.output_images)
        ? options.output_images.filter((v) => typeof v === "string" && v.trim())
        : ["sysupgrade"];
    return {
        profile_id: String(request?.profile_id || "").trim(),
        platform: String(request?.platform || "").trim(),
        target: String(request?.target || "").trim(),
        subtarget: String(request?.subtarget || "").trim(),
        version: String(request?.version || "").trim(),
        options: {
            force_rebuild: Boolean(options.force_rebuild),
            debug: Boolean(options.debug),
            output_images: outputImages.length ? outputImages : ["sysupgrade"],
        },
    };
}

async function fetchBuild(buildId) {
    return apiJson(`${API}/build/${encodeURIComponent(buildId)}`);
}

async function viewBuildRequest(buildId, anchorEl) {
    showBuildsError("");
    hideBuildMessageDetails();
    const tooltip = el("builds-request-tooltip");
    if (!tooltip.classList.contains("hidden") && tooltip.dataset.buildId === String(buildId || "")) {
        hideBuildRequestDetails();
        return;
    }
    const build = await fetchBuild(buildId);
    showBuildRequestDetails(build, anchorEl);
}

async function viewBuildMessage(buildId, fullMessage, anchorEl) {
    showBuildsError("");
    hideBuildRequestDetails();
    const tooltip = el("builds-message-tooltip");
    if (!tooltip.classList.contains("hidden") && tooltip.dataset.buildId === String(buildId || "")) {
        hideBuildMessageDetails();
        return;
    }
    showBuildMessageDetails(buildId, fullMessage, anchorEl, "Build message");
}

function formatBuildLogs(payload = {}) {
    const state = String(payload?.state || "").trim() || "unknown";
    const phase = String(payload?.phase || "").trim() || "n/a";
    const stdout = String(payload?.stdout || "");
    const stderr = String(payload?.stderr || "");
    const stdoutTruncated = Boolean(payload?.stdout_truncated);
    const stderrTruncated = Boolean(payload?.stderr_truncated);
    const updatedAt = String(payload?.updated_at || "");
    const chunks = [
        `state: ${state}`,
        `phase: ${phase}`,
        `updated_at: ${updatedAt || "-"}`,
        "",
        "[STDOUT]",
        stdout || "<empty>",
        stdoutTruncated ? "\n...stdout truncated..." : "",
        "",
        "[STDERR]",
        stderr || "<empty>",
        stderrTruncated ? "\n...stderr truncated..." : "",
    ];
    return chunks.join("\n");
}

async function fetchBuildLogs(buildId, limit = 24000) {
    return apiJson(`${API}/build/${encodeURIComponent(buildId)}/logs?limit=${encodeURIComponent(String(limit))}`);
}

async function viewBuildLogs(buildId, anchorEl) {
    showBuildsError("");
    hideBuildRequestDetails();
    const tooltip = el("builds-message-tooltip");
    if (!tooltip.classList.contains("hidden") && tooltip.dataset.buildId === String(buildId || "")) {
        hideBuildMessageDetails();
        return;
    }
    const payload = await fetchBuildLogs(buildId);
    showBuildMessageDetails(buildId, formatBuildLogs(payload), anchorEl, "Build logs");
}

async function createBuild() {
    showBuildsError("");
    const profileId = el("builds-profile").value.trim();
    const platform = el("builds-platform").value.trim();
    const target = el("builds-target").value.trim();
    const subtarget = el("builds-subtarget").value.trim();
    const version = el("builds-version").value.trim();
    const forceRebuild = el("builds-force").checked;
    const debug = el("builds-debug").checked;
    const outputImages = selectedBuildOutputImages();

    if (!profileId) {
        showBuildsError("Select a profile");
        return;
    }
    if (!platform) {
        showBuildsError("Platform is required");
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
                platform,
                target,
                subtarget,
                version,
                options: {
                    force_rebuild: forceRebuild,
                    debug,
                    output_images: outputImages.length ? outputImages : ["sysupgrade"],
                },
            },
        }),
    });
    await refreshBuilds();
}

async function rebuildBuild(buildId) {
    showBuildsError("");
    const sourceBuild = await fetchBuild(buildId);
    const request = normalizeBuildRequest(sourceBuild?.request || {});

    if (!request.profile_id || !request.platform || !request.target || !request.subtarget || !request.version) {
        throw new Error(`Build ${buildId} has invalid request payload`);
    }

    await apiJson(`${API}/build`, {
        method: "POST",
        body: JSON.stringify({
            request: {
                ...request,
                options: {
                    ...request.options,
                    force_rebuild: true,
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

async function deleteSelectedBuilds() {
    await deleteSelectedItems({
        scope: "builds",
        errorSetter: showBuildsError,
        deleteOne: async (buildId) => {
            await apiJson(`${API}/build/${encodeURIComponent(buildId)}`, { method: "DELETE" });
        },
        successRefresh: refreshBuilds,
        entityLabel: "build(s)",
    });
}

/* ---------------- Files ---------------- */

function showFilesError(err = "") {
    const msg = String(err || "").trim();
    el("files-error").textContent = msg;
    el("files-error").classList.toggle("hidden", !msg);
}

function renderFilesTable(rows) {
    const sortedRows = sortByUpdatedAtDesc(rows);
    const visibleSources = new Set(
        sortedRows.map((r) => String(r?.source_path || r?.path || "").trim()).filter(Boolean)
    );
    Array.from(fileTargetDrafts.keys()).forEach((sourcePath) => {
        if (!visibleSources.has(sourcePath)) fileTargetDrafts.delete(sourcePath);
    });
    const html = `
    <table>
      <thead>
        <tr><th>source_path</th><th>target_path</th><th>size</th><th>updated_at</th><th></th></tr>
      </thead>
      <tbody>
        ${sortedRows.map((r) => {
            const rowSource = String(r.source_path ?? r.path ?? "").trim();
            const fallbackTarget = toUiRootfsDir(r.target_path ?? r.source_path ?? r.path ?? "");
            const currentTarget = fileTargetDrafts.has(rowSource) ? String(fileTargetDrafts.get(rowSource) || "") : fallbackTarget;
            return `
          <tr>
            <td>${escapeHtml(rowSource)}</td>
            <td>
              <div class="file-target-edit">
                <input
                  type="text"
                  data-file-target-input
                  data-source-path="${escapeAttr(rowSource)}"
                  data-default="${escapeAttr(fallbackTarget)}"
                  value="${escapeAttr(currentTarget)}"
                />
                <div class="file-target-actions">
                  <button type="button" data-act="save-target" data-source-path="${escapeAttr(rowSource)}">Save</button>
                  <button type="button" data-act="reset-target" data-source="${escapeAttr(toUiRootfsDir(sourceDir(rowSource)))}" data-source-path="${escapeAttr(rowSource)}">Reset</button>
                </div>
              </div>
            </td>
            <td>${escapeHtml(String(r.size ?? ""))}</td>
            <td>${renderUpdatedAtCell(r.updated_at)}</td>
            <td class="actions">
              <button type="button" data-act="del" data-path="${escapeAttr(r.source_path ?? r.path ?? "")}">Delete</button>
            </td>
          </tr>
        `;
    }).join("")}
      </tbody>
    </table>
  `;
    el("files-table").innerHTML = html;

    el("files-table").querySelectorAll("button[data-act='save-target']").forEach((b) => {
        b.addEventListener("click", async () => {
            const sourcePath = String(b.getAttribute("data-source-path") || "").trim();
            const row = b.closest("tr");
            const input = row?.querySelector("input[data-file-target-input]");
            const nextTarget = String(input?.value || "").trim();
            await updateFileTarget(sourcePath, nextTarget);
        });
    });
    el("files-table").querySelectorAll("button[data-act='reset-target']").forEach((b) => {
        b.addEventListener("click", async () => {
            const sourcePathKey = String(b.getAttribute("data-source-path") || "").trim();
            const sourcePath = String(b.getAttribute("data-source") || "").trim();
            await updateFileTarget(sourcePathKey, sourcePath);
        });
    });
    el("files-table").querySelectorAll("input[data-file-target-input]").forEach((input) => {
        input.addEventListener("input", () => {
            const sourcePath = String(input.getAttribute("data-source-path") || "").trim();
            if (!sourcePath) return;
            fileTargetDrafts.set(sourcePath, String(input.value || ""));
        });
        input.addEventListener("keydown", async (event) => {
            if (event.key !== "Enter") return;
            event.preventDefault();
            const sourcePath = String(input.getAttribute("data-source-path") || "").trim();
            const nextTarget = String(input.value || "").trim();
            await updateFileTarget(sourcePath, nextTarget);
        });
    });
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
    const targetInput = el("files-target-path");
    const targetPath = String(targetInput?.value || "").trim();
    const files = Array.from(input.files || []);
    if (!files.length) {
        showFilesError("Select at least one file");
        return;
    }

    for (const file of files) {
        const fd = new FormData();
        fd.append("file", file, file.name);
        if (targetPath) {
            const baseDir = fromUiRootfsDir(targetPath);
            if (!baseDir) {
                showFilesError("invalid rootfs target directory");
                return;
            }
            fd.append("target_path", baseDir);
        }
        await apiJson(`${API}/file`, { method: "POST", body: fd });
    }

    input.value = "";
    if (targetInput) targetInput.value = "";
    await refreshFiles();
}

async function deleteFile(path) {
    showFilesError("");
    await apiJson(`${API}/file/${encodeURIComponent(path)}`, { method: "DELETE" });
    await refreshFiles();
}

async function updateFileTarget(sourcePath, nextTarget) {
    showFilesError("");
    const normalizedSource = String(sourcePath || "").trim();
    if (!normalizedSource) {
        showFilesError("source_path is required");
        return;
    }
    const normalized = fromUiRootfsDir(nextTarget);
    if (!normalized) {
        showFilesError("target_path directory is required (example: /etc/dropbear)");
        return;
    }
    fileTargetDrafts.set(normalizedSource, String(nextTarget || ""));
    await apiJson(`${API}/file-meta/${encodeURIComponent(normalizedSource)}`, {
        method: "PUT",
        body: JSON.stringify({ target_path: normalized }),
    });
    fileTargetDrafts.delete(normalizedSource);
    await refreshFiles();
}

function sourceDir(path) {
    const value = String(path || "").trim().replace(/\\/g, "/");
    if (!value) return ".";
    const idx = value.lastIndexOf("/");
    if (idx < 0) return ".";
    const dir = value.slice(0, idx).replace(/\/+$/, "");
    return dir || ".";
}

function normalizeDirPath(path) {
    const value = String(path || "").trim().replace(/\\/g, "/");
    if (!value) return "";
    if (value === ".") return ".";
    const dir = value.replace(/^\/+/, "").replace(/\/+$/, "");
    if (!dir) return "";
    const parts = dir.split("/");
    if (parts.some((part) => part === "" || part === "." || part === "..")) return "";
    return dir;
}

function toUiRootfsDir(path) {
    const value = String(path || "").trim().replace(/\\/g, "/");
    if (!value || value === ".") return "/";
    return `/${value.replace(/^\/+/, "")}`;
}

function fromUiRootfsDir(path) {
    const value = String(path || "").trim().replace(/\\/g, "/");
    if (!value) return "";
    if (value === "/" || value === ".") return ".";
    return normalizeDirPath(value);
}

async function deleteSelectedLists() {
    await deleteSelectedItems({
        scope: "lists",
        errorSetter: showListsError,
        deleteOne: async (id) => {
            await apiJson(`${API}/list/${encodeURIComponent(id)}`, { method: "DELETE" });
        },
        successRefresh: refreshLists,
        entityLabel: "list(s)",
    });
}

async function deleteSelectedProfiles() {
    await deleteSelectedItems({
        scope: "profiles",
        errorSetter: showProfilesError,
        deleteOne: async (id) => {
            await apiJson(`${API}/profile/${encodeURIComponent(id)}`, { method: "DELETE" });
        },
        successRefresh: refreshProfiles,
        entityLabel: "profile(s)",
    });
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
    const config = loadApiConfigFromStorage();
    API = buildApiBase(config.address, config.path);
    const addressInput = el("api-backend-address");
    const pathInput = el("api-path");
    if (addressInput) addressInput.value = config.address;
    if (pathInput) pathInput.value = config.path;
    wireApiBaseControls();

    el("tab-builds").addEventListener("click", () => setTab("builds"));
    el("tab-lists").addEventListener("click", () => setTab("lists"));
    el("tab-profiles").addEventListener("click", () => setTab("profiles"));
    el("tab-files").addEventListener("click", () => setTab("files"));
    el("tab-settings").addEventListener("click", () => setTab("settings"));
    wireTabKeyboardNavigation();

    el("builds-refresh").addEventListener("click", () => refreshBuilds().catch((e) => showBuildsError(e.message || e)));
    el("builds-select-all").addEventListener("click", () => setVisibleRowSelection("builds", true));
    el("builds-deselect-all").addEventListener("click", () => setVisibleRowSelection("builds", false));
    el("builds-delete-selected").addEventListener("click", () => deleteSelectedBuilds().catch((e) => showBuildsError(e.message || e)));
    el("builds-create").addEventListener("click", () => createBuild().catch((e) => showBuildsError(e.message || e)));
    el("builds-version").addEventListener("change", () => syncBuildSelectors().catch((e) => showBuildsError(e.message || e)));
    el("builds-target").addEventListener("change", () => syncBuildSelectors().catch((e) => showBuildsError(e.message || e)));
    el("builds-subtarget").addEventListener("change", () => syncBuildSelectors().catch((e) => showBuildsError(e.message || e)));
    wireBuildImagesSelection();
    el("builds-request-tooltip-copy").addEventListener("click", async (event) => {
        const tooltip = el("builds-request-tooltip");
        const requestJson = String(tooltip.dataset.requestJson || "");
        if (!requestJson) return;
        const btn = event.currentTarget;
        if (!(btn instanceof HTMLButtonElement)) return;
        await copyText(requestJson);
        btn.classList.add("copied");
        btn.setAttribute("title", "Copied");
        btn.setAttribute("aria-label", "Copied");
        window.setTimeout(() => {
            btn.classList.remove("copied");
            btn.setAttribute("title", "Copy request JSON");
            btn.setAttribute("aria-label", "Copy request JSON");
        }, 900);
    });
    el("builds-message-tooltip-copy").addEventListener("click", async (event) => {
        const tooltip = el("builds-message-tooltip");
        const messageText = String(tooltip.dataset.messageText || "");
        if (!messageText) return;
        const btn = event.currentTarget;
        if (!(btn instanceof HTMLButtonElement)) return;
        await copyText(messageText);
        btn.classList.add("copied");
        btn.setAttribute("title", "Copied");
        btn.setAttribute("aria-label", "Copied");
        window.setTimeout(() => {
            btn.classList.remove("copied");
            btn.setAttribute("title", "Copy full message");
            btn.setAttribute("aria-label", "Copy full message");
        }, 900);
    });
    document.addEventListener("click", (event) => {
        const requestTooltip = el("builds-request-tooltip");
        const messageTooltip = el("builds-message-tooltip");
        if (requestTooltip.classList.contains("hidden") && messageTooltip.classList.contains("hidden")) return;
        const target = event.target;
        if (!(target instanceof Node)) return;
        if (requestTooltip.contains(target) || messageTooltip.contains(target)) return;
        if (target instanceof Element && target.closest('button[data-act="params"], button[data-act="show-message"], button[data-act="logs"]')) return;
        hideBuildTooltips();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") hideBuildTooltips();
    });
    window.addEventListener("resize", hideBuildTooltips);
    window.addEventListener("scroll", hideBuildTooltips, { passive: true });

    el("lists-refresh").addEventListener("click", () => refreshLists().catch((e) => showListsError(e.message || e)));
    el("lists-create").addEventListener("click", () => openListEditor(null).catch((e) => showListsError(e.message || e)));
    el("lists-sort-name").addEventListener("click", () => {
        setEntitySort("lists", "name");
        refreshLists().catch((e) => showListsError(e.message || e));
    });
    el("lists-sort-updated").addEventListener("click", () => {
        setEntitySort("lists", "updated");
        refreshLists().catch((e) => showListsError(e.message || e));
    });
    el("lists-search").addEventListener("input", (event) => {
        entitySearch.lists = String(event.target?.value || "");
        renderListsTable();
    });
    el("lists-import-run").addEventListener("click", () => importLists().catch((e) => showListsError(e.message || e)));
    el("lists-select-all").addEventListener("click", () => setVisibleRowSelection("lists", true));
    el("lists-deselect-all").addEventListener("click", () => setVisibleRowSelection("lists", false));
    el("lists-delete-selected").addEventListener("click", () => deleteSelectedLists().catch((e) => showListsError(e.message || e)));

    el("profiles-refresh").addEventListener("click", () => refreshProfiles().catch((e) => showProfilesError(e.message || e)));
    el("profiles-create").addEventListener("click", () => openProfileEditor(null).catch((e) => showProfilesError(e.message || e)));
    el("profiles-sort-name").addEventListener("click", () => {
        setEntitySort("profiles", "name");
        refreshProfiles().catch((e) => showProfilesError(e.message || e));
    });
    el("profiles-sort-updated").addEventListener("click", () => {
        setEntitySort("profiles", "updated");
        refreshProfiles().catch((e) => showProfilesError(e.message || e));
    });
    el("profiles-search").addEventListener("input", (event) => {
        entitySearch.profiles = String(event.target?.value || "");
        renderProfilesTable();
    });
    el("profiles-select-all").addEventListener("click", () => setVisibleRowSelection("profiles", true));
    el("profiles-deselect-all").addEventListener("click", () => setVisibleRowSelection("profiles", false));
    el("profiles-delete-selected").addEventListener("click", () => deleteSelectedProfiles().catch((e) => showProfilesError(e.message || e)));
    el("files-refresh").addEventListener("click", () => refreshFiles().catch((e) => showFilesError(e.message || e)));
    el("files-upload").addEventListener("click", () => uploadFiles().catch((e) => showFilesError(e.message || e)));

    setTab("builds");
    hideBuildTooltips();
    if (buildsAutoRefreshHandle === null) {
        buildsAutoRefreshHandle = window.setInterval(() => {
            if (el("view-builds").classList.contains("hidden")) return;
            refreshBuilds().catch(() => { });
        }, BUILDS_AUTO_REFRESH_MS);
    }
    refreshAllViews();
}

boot();
