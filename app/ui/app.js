const stage = document.querySelector("#stage");
const settingsBtn = document.querySelector("#settings-btn");
const settingsPop = document.querySelector("#settings-pop");
const zaloMeta = document.querySelector("#zalo-meta");
const zaloAction = document.querySelector("#zalo-action");
const job = document.querySelector("#job");
const jobFill = document.querySelector("#job-fill");
const jobMsg = document.querySelector("#job-msg");
const banner = document.querySelector("#banner");
const modal = document.querySelector("#modal");
const modalTitle = document.querySelector("#modal-title");
const modalBody = document.querySelector("#modal-body");
const modalCancel = document.querySelector("#modal-cancel");
const modalOk = document.querySelector("#modal-ok");

const preview = new URLSearchParams(location.search).has("preview");
let state = null;
let pendingModal = null;
let gridKey = "";
let adding = false;
let editing = null;
let storageId = null;

const mock = {
  zalo: { installed: false, version: null },
  settings: { autoUpdate: true, efficiency: true, startWithWindows: false },
  accounts: [],
  job: null,
  error: null,
};

function sealLetter(name) {
  const trimmed = name.trim();
  return trimmed ? trimmed.charAt(0).toUpperCase() : "?";
}

const ICONS = {
  edit: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M9.2 2.6l4.2 4.2L6 14.2H2.8V11L9.2 2.6z"/><path d="M8 3.8l4.2 4.2"/></svg>',
  storage: '<svg viewBox="0 0 16 16" aria-hidden="true"><ellipse cx="8" cy="4" rx="5" ry="2"/><path d="M3 4v8c0 1.1 2.2 2 5 2s5-.9 5-2V4"/><path d="M3 8c0 1.1 2.2 2 5 2s5-.9 5-2"/></svg>',
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function iconButton(action, label, icon) {
  const button = el("button", "icon-btn");
  button.type = "button";
  button.dataset.action = action;
  button.title = label;
  button.setAttribute("aria-label", label);
  button.innerHTML = ICONS[icon];
  return button;
}

function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value >= 1024 ** 3) {
    const gb = value / 1024 ** 3;
    return `${gb >= 10 ? gb.toFixed(0) : gb.toFixed(1)} GB`;
  }
  if (value >= 1024 ** 2) {
    const mb = value / 1024 ** 2;
    return `${mb >= 10 ? mb.toFixed(0) : mb.toFixed(1)} MB`;
  }
  if (value >= 1024) return `${Math.max(1, Math.round(value / 1024))} KB`;
  return "0 MB";
}

function formatRam(bytes) {
  const mb = (Number(bytes) || 0) / 1024 ** 2;
  return `${mb.toFixed(1)} MB`;
}

function idleLabel(account, efficiencyOn) {
  if (!account.running || !efficiencyOn) return "";
  if (account.saving) return "CPU thấp, RAM được trả bớt. Vẫn nhận tin.";
  const left = Math.max(0, 300 - (Number(account.idleFor) || 0));
  const minutes = Math.max(1, Math.ceil(left / 60));
  return `Giảm RAM sau ${minutes} phút không dùng`;
}

function showBanner(message) {
  banner.hidden = !message;
  banner.textContent = message || "";
}

function renderJob(next) {
  if (!next.job) {
    job.hidden = true;
    return;
  }
  job.hidden = false;
  jobMsg.textContent = next.job.message || "";
  const bar = job.querySelector(".job-bar");
  if (typeof next.job.progress === "number") {
    bar.classList.remove("indeterminate");
    jobFill.style.width = `${Math.round(next.job.progress * 100)}%`;
  } else {
    bar.classList.add("indeterminate");
    jobFill.style.width = "";
  }
}

function renderPrefs(next) {
  const installed = Boolean(next.zalo && next.zalo.installed);
  settingsBtn.hidden = !installed;
  if (!installed) closeSettings();
  const settings = next.settings || {};
  settingsPop.querySelectorAll("[data-pref]").forEach((button) => {
    const on = settings[button.dataset.pref] !== false;
    button.setAttribute("aria-checked", on ? "true" : "false");
  });
}

function closeSettings() {
  settingsPop.hidden = true;
  settingsBtn.classList.remove("is-on");
  settingsBtn.setAttribute("aria-expanded", "false");
}

function toggleSettings() {
  if (settingsPop.hidden) {
    closePopover();
    settingsPop.hidden = false;
    settingsBtn.classList.add("is-on");
    settingsBtn.setAttribute("aria-expanded", "true");
    return;
  }
  closeSettings();
}

function renderHeader(next) {
  const installed = Boolean(next.zalo.installed);
  const version = next.zalo.version ? next.zalo.version.split(".").slice(0, 3).join(".") : "";
  const latest = next.zalo.latest ? next.zalo.latest.split(".").slice(0, 3).join(".") : "";
  const newer = Boolean(next.zalo.updateAvailable);
  const updating = Boolean(next.job && next.job.kind === "update");
  zaloMeta.hidden = !installed;
  zaloAction.hidden = !installed || (!newer && !updating);
  if (!installed) return;
  zaloMeta.textContent = `Zalo ${version}`;
  zaloAction.textContent = latest && newer ? `Cập nhật ${latest}` : "Cập nhật";
  zaloAction.disabled = Boolean(next.job);
}

function accountCard(account, installed, efficiencyOn) {
  const saving = Boolean(account.saving);
  const card = el("article", "card" + (account.running ? " running" : "") + (saving ? " saving" : ""));
  card.dataset.id = account.id;
  const top = el("div", "card-top");
  const seal = el("button", "seal", account.icon ? "" : sealLetter(account.name));
  seal.type = "button";
  seal.dataset.action = "edit";
  seal.title = "Sửa tên và logo";
  if (account.icon) {
    seal.classList.add("seal-photo");
    const image = el("img", "seal-img");
    image.src = account.icon;
    image.alt = "";
    seal.append(image);
  }
  top.append(seal);
  const copy = el("div");
  copy.append(el("h2", "name", account.name));
  const status = el(
    "p",
    "status" + (saving ? " saving" : ""),
    saving ? "Đang tiết kiệm" : account.running ? "Đang mở" : "Đang tắt",
  );
  if (saving) status.title = "Vẫn nhận thông báo và cuộc gọi";
  copy.append(status);
  const note = el("p", "status-note", idleLabel(account, efficiencyOn));
  note.dataset.usage = "idle";
  copy.append(note);
  top.append(copy);
  card.append(top);
  card.append(meterRow(account));
  card.append(bootSwitch(account));

  const actions = el("div", "card-actions");
  const main = el("button", "btn btn-primary", account.running ? "Đóng" : "Mở");
  main.type = "button";
  main.dataset.action = account.running ? "close" : "open";
  main.disabled = !installed && !account.running;
  const tools = el("div", "card-tools");
  tools.append(iconButton("edit", "Sửa", "edit"), iconButton("storage", "Dung lượng", "storage"));
  const remove = el("button", "btn-text", "Xóa");
  remove.type = "button";
  remove.dataset.action = "delete";
  actions.append(main, tools, remove);
  card.append(actions);
  return card;
}

function meterRow(account) {
  const row = el("div", "meters");
  const disk = el("div", "meter");
  disk.append(el("span", "", "Đĩa"));
  const diskValue = el("strong", "", formatBytes(account.disk));
  diskValue.dataset.usage = "disk";
  disk.append(diskValue);
  row.append(disk);
  if (account.running) {
    const ram = el("div", "meter");
    ram.title = "Cùng cột Bộ nhớ trong Task Manager";
    ram.append(el("span", "", "RAM"));
    const ramValue = el("strong", "", formatRam(account.ram));
    ramValue.dataset.usage = "ram";
    ram.append(ramValue);
    row.append(ram);
  }
  return row;
}

function bootSwitch(account) {
  const button = el("button", "boot");
  button.type = "button";
  button.dataset.boot = "1";
  button.setAttribute("role", "switch");
  button.setAttribute("aria-checked", account.openWithWindows ? "true" : "false");
  button.append(el("span", "", "Mở cùng máy"));
  button.append(el("span", "knob"));
  button.title = "Khi đăng nhập Windows, tài khoản này chạy ẩn. Bấm khay Due để hiện cửa sổ.";
  return button;
}

function storageRow(label, bytes, usageName, ram) {
  const row = el("div", "usage-row");
  row.append(el("span", "", label));
  const value = el("strong", "", ram ? formatRam(bytes) : formatBytes(bytes));
  value.dataset.usage = usageName;
  row.append(value);
  return row;
}

function storagePanel(account) {
  const panel = el("div", "menu menu-float");
  panel.dataset.popover = "storage";
  const head = el("div", "menu-head");
  head.append(el("p", "menu-title", "Dung lượng"));
  const total = el("strong", "", formatBytes(account.disk));
  total.dataset.usage = "disk";
  head.append(total);
  panel.append(head);
  const list = el("div", "usage-list");
  list.append(storageRow("Dữ liệu hệ thống", account.system, "system"));
  list.append(storageRow("Bộ nhớ đệm", account.cache, "cache"));
  list.append(storageRow("Ảnh, video, file", account.media, "media"));
  list.append(storageRow("Phần còn lại", account.other, "other"));
  if (account.running) list.append(storageRow("RAM đang dùng", account.ram, "ram", true));
  panel.append(list);
  const note = el("p", "menu-note", `${account.zaloLocation || "Windows (C:)"} chỉ là ổ hồ sơ Windows. Chat nằm trong thư mục tài khoản.`);
  const path = el("p", "path-line", account.path || "");
  path.title = account.path || "";
  path.dataset.usage = "path";
  panel.append(note, path);
  const actions = el("div", "menu-actions split");
  const open = el("button", "btn btn-ghost", "Mở thư mục");
  open.type = "button";
  open.dataset.action = "open-folder";
  const clear = el("button", "btn btn-ghost", "Xóa bộ nhớ đệm");
  clear.type = "button";
  clear.dataset.action = "clear-cache";
  actions.append(open, clear);
  panel.append(actions);
  return panel;
}

function editPopover(account) {
  const panel = el("div", "menu menu-float");
  panel.dataset.popover = "edit";
  panel.append(el("p", "menu-title", "Sửa tài khoản"));
  const field = el("label", "field");
  field.append(el("span", "field-label", "Tên"));
  const input = el("input", "name-input");
  input.value = account.name;
  input.maxLength = 40;
  input.setAttribute("aria-label", "Tên tài khoản");
  field.append(input);
  const logo = el("button", "btn btn-ghost", "Chọn logo PNG");
  logo.type = "button";
  logo.dataset.action = "icon";
  const actions = el("div", "menu-actions");
  const cancel = el("button", "btn btn-ghost", "Hủy");
  cancel.type = "button";
  cancel.dataset.action = "cancel-rename";
  const save = el("button", "btn btn-primary", "Lưu");
  save.type = "button";
  save.dataset.action = "save-name";
  actions.append(cancel, save);
  panel.append(field, logo, actions);
  queueMicrotask(() => input.focus());
  return panel;
}

function closePopover() {
  editing = null;
  storageId = null;
  document.querySelectorAll(".menu-float").forEach((node) => node.remove());
  stage.querySelectorAll(".icon-btn.is-on").forEach((button) => button.classList.remove("is-on"));
}

function placeMenu(panel, anchor) {
  const rect = anchor.getBoundingClientRect();
  const width = panel.offsetWidth;
  const height = panel.offsetHeight;
  let left = Math.min(rect.right - width, window.innerWidth - width - 12);
  left = Math.max(12, left);
  let top = rect.bottom + 8;
  if (top + height > window.innerHeight - 12) top = Math.max(12, rect.top - height - 8);
  panel.style.left = `${left}px`;
  panel.style.top = `${top}px`;
}

function mountPopover() {
  document.querySelectorAll(".menu-float").forEach((node) => node.remove());
  stage.querySelectorAll(".icon-btn.is-on").forEach((button) => button.classList.remove("is-on"));
  const id = editing || storageId;
  if (!id || !state) return;
  const account = state.accounts.find((item) => item.id === id);
  const card = stage.querySelector(`[data-id="${id}"]`);
  if (!account || !card) return;
  const action = editing ? "edit" : "storage";
  const panel = editing ? editPopover(account) : storagePanel(account);
  panel.dataset.for = id;
  panel.dataset.id = id;
  document.body.append(panel);
  const button = card.querySelector(`.icon-btn[data-action="${action}"]`);
  if (button) {
    button.classList.add("is-on");
    placeMenu(panel, button);
  }
}

function addCard() {
  const button = el("button", "add");
  button.type = "button";
  button.dataset.action = "start-add";
  button.append(el("strong", "", "Thêm tài khoản"));
  button.append(el("span", "", "Một thẻ, một lần đăng nhập"));
  return button;
}

function addForm() {
  const card = el("form", "card");
  card.dataset.adding = "1";
  const input = el("input", "add-input");
  input.name = "name";
  input.placeholder = "Tên gợi nhớ";
  input.maxLength = 40;
  input.setAttribute("aria-label", "Tên tài khoản mới");
  const actions = el("div", "card-actions");
  const save = el("button", "btn btn-primary", "Tạo");
  save.type = "submit";
  const cancel = el("button", "btn-text", "Hủy");
  cancel.type = "button";
  cancel.dataset.action = "cancel-add";
  actions.append(save, cancel);
  card.append(input, actions);
  queueMicrotask(() => input.focus());
  return card;
}

function renderStage(next) {
  stage.replaceChildren();
  const fresh = !next.zalo.installed && next.accounts.length === 0 && !adding;
  stage.classList.toggle("stage-install", fresh);
  if (fresh) {
    const panel = el("section", "install");
    panel.append(el("h2", "", "Cài Zalo PC"));
    panel.append(el("p", "", "Due tải bộ cài chính thức của Zalo, rồi mở mỗi tài khoản trong một thư mục riêng. Cập nhật một lần, mọi thẻ dùng bản mới."));
    const button = el("button", "btn btn-primary", "Cài Zalo PC");
    button.type = "button";
    button.dataset.action = "install";
    button.disabled = Boolean(next.job);
    panel.append(button);
    stage.append(panel);
    return;
  }

  const grid = el("section", "grid");
  if (!next.zalo.installed) {
    const panel = el("section", "install");
    panel.append(el("h2", "", "Cài lại Zalo PC"));
    panel.append(el("p", "", "Các thẻ vẫn còn. Cài Zalo xong là mở được tiếp."));
    const button = el("button", "btn btn-primary", "Cài Zalo PC");
    button.type = "button";
    button.dataset.action = "install";
    button.disabled = Boolean(next.job);
    panel.append(button);
    stage.append(panel);
  }
  for (const account of next.accounts) {
    grid.append(accountCard(account, next.zalo.installed, Boolean(next.settings && next.settings.efficiency !== false)));
  }
  grid.append(adding ? addForm() : addCard());
  stage.append(grid);
  mountPopover();
}

function gridSnapshot(next) {
  return JSON.stringify({
    installed: Boolean(next.zalo && next.zalo.installed),
    accounts: (next.accounts || []).map((account) => ({
      id: account.id,
      name: account.name,
      running: account.running,
      saving: account.saving,
      icon: account.icon,
    })),
    job: Boolean(next.job),
    adding,
  });
}

function patchUsage(next) {
  const efficiencyOn = Boolean(next.settings && next.settings.efficiency !== false);
  for (const account of next.accounts || []) {
    const nodes = [stage.querySelector(`[data-id="${account.id}"]`), document.querySelector(`.menu-float[data-for="${account.id}"]`)];
    for (const root of nodes) {
      if (!root) continue;
      for (const key of ["disk", "system", "cache", "media", "other", "ram"]) {
        const node = root.querySelector(`[data-usage="${key}"]`);
        if (!node) continue;
        node.textContent = key === "ram" ? formatRam(account.ram) : formatBytes(account[key]);
      }
      const note = root.querySelector("[data-usage='idle']");
      if (note) note.textContent = idleLabel(account, efficiencyOn);
      const boot = root.querySelector("[data-boot]");
      if (boot) boot.setAttribute("aria-checked", account.openWithWindows ? "true" : "false");
    }
  }
}

function draw(next, options) {
  state = next;
  renderHeader(next);
  renderPrefs(next);
  renderJob(next);
  showBanner(next.error);
  if (options) {
    if ("adding" in options) adding = Boolean(options.adding);
    if ("editing" in options) editing = options.editing || null;
    if ("storage" in options) storageId = options.storage || null;
  }
  const typing = document.activeElement && document.activeElement.matches("input");
  if (typing && !options) {
    patchUsage(next);
    return;
  }
  const key = gridSnapshot(next);
  if (key === gridKey) {
    patchUsage(next);
    return;
  }
  gridKey = key;
  renderStage(next);
}

async function call(method, ...args) {
  if (preview) return mockCall(method, ...args);
  try {
    const result = await window.pywebview.api[method](...args);
    if (!result.ok) showBanner(result.error || "Không làm được");
    await refresh();
    return result;
  } catch (error) {
    showBanner("Không làm được");
  }
}

function mockCall(method, ...args) {
  if (method === "add_account") {
    mock.accounts.push({ id: String(Date.now()), name: args[0], running: false });
  } else if (method === "rename_account") {
    const account = mock.accounts.find((item) => item.id === args[0]);
    if (account) account.name = args[1];
  } else if (method === "remove_account") {
    mock.accounts = mock.accounts.filter((item) => item.id !== args[0]);
  } else if (method === "open_account" || method === "close_account") {
    const account = mock.accounts.find((item) => item.id === args[0]);
    if (account) account.running = method === "open_account";
  } else if (method === "install_zalo" || method === "update_zalo") {
    mock.zalo = { installed: true, version: "26.9.10.0" };
    mock.job = null;
  } else if (method === "set_setting") {
    mock.settings[args[0]] = Boolean(args[1]);
    if (args[0] === "efficiency" && !args[1]) {
      mock.accounts.forEach((account) => {
        account.saving = false;
      });
    }
    if (args[0] === "startWithWindows" && !args[1]) {
      mock.accounts.forEach((account) => {
        account.openWithWindows = false;
      });
    }
  } else if (method === "set_account_startup") {
    const account = mock.accounts.find((item) => item.id === args[0]);
    if (account) account.openWithWindows = Boolean(args[1]);
    if (args[1]) mock.settings.startWithWindows = true;
  }
  mock.error = null;
  draw(mock);
  return { ok: true };
}

async function refresh() {
  if (preview) return;
  const next = await window.pywebview.api.state();
  draw(next);
}

function openModal(title, body, okLabel, action) {
  pendingModal = action;
  modalTitle.textContent = title;
  modalBody.textContent = body;
  modalOk.textContent = okLabel;
  modal.hidden = false;
  modalCancel.focus();
}

function closeModal() {
  modal.hidden = true;
  pendingModal = null;
}

document.addEventListener("click", (event) => {
  const boot = event.target.closest("[data-boot]");
  if (boot) {
    const id = boot.closest("[data-id]") ? boot.closest("[data-id]").dataset.id : "";
    if (!id || !state) return;
    const enabled = boot.getAttribute("aria-checked") !== "true";
    const account = state.accounts.find((item) => item.id === id);
    if (account) account.openWithWindows = enabled;
    if (enabled) {
      if (!state.settings) state.settings = {};
      state.settings.startWithWindows = true;
    }
    boot.setAttribute("aria-checked", enabled ? "true" : "false");
    call("set_account_startup", id, enabled);
    return;
  }
  const trigger = event.target.closest("[data-action]");
  if (!trigger) return;
  const card = trigger.closest("[data-id]");
  const id = card ? card.dataset.id : "";
  const action = trigger.dataset.action;
  if (action === "install") call("install_zalo");
  if (action === "start-add") {
    closePopover();
    closeSettings();
    draw(state, { adding: true });
  }
  if (action === "cancel-add") draw(state, { adding: false });
  if (action === "cancel-rename") closePopover();
  if (action === "open") call("open_account", id);
  if (action === "close") call("close_account", id);
  if (action === "edit") {
    closeSettings();
    if (editing === id) closePopover();
    else {
      editing = id;
      storageId = null;
      mountPopover();
    }
  }
  if (action === "storage") {
    closeSettings();
    if (storageId === id) closePopover();
    else {
      storageId = id;
      editing = null;
      mountPopover();
    }
  }
  if (action === "icon") call("choose_icon", id);
  if (action === "open-folder") call("open_folder", id);
  if (action === "clear-cache") {
    openModal(
      "Xóa bộ nhớ đệm?",
      "Cache của thẻ này sẽ mất. Tin nhắn không bị xóa. Tài khoản phải đang tắt.",
      "Xóa bộ nhớ đệm",
      () => call("clear_cache", id),
    );
  }
  if (action === "save-name") {
    const input = card.querySelector("input");
    const value = input ? input.value : "";
    closePopover();
    call("rename_account", id, value);
  }
  if (action === "delete") {
    const account = state.accounts.find((item) => item.id === id);
    openModal(
      `Xóa ${account ? account.name : "tài khoản"}?`,
      "Thư mục chat của thẻ này trên máy sẽ mất. Tài khoản Zalo không bị khóa.",
      "Xóa",
      () => call("remove_account", id),
    );
  }
});

stage.addEventListener("submit", (event) => {
  const form = event.target.closest("form");
  if (!form) return;
  event.preventDefault();
  const input = form.querySelector("input");
  call("add_account", input.value);
});

settingsPop.addEventListener("click", (event) => {
  const button = event.target.closest("[data-pref]");
  if (!button || !state) return;
  const key = button.dataset.pref;
  const enabled = button.getAttribute("aria-checked") !== "true";
  if (!state.settings) state.settings = {};
  state.settings[key] = enabled;
  button.setAttribute("aria-checked", enabled ? "true" : "false");
  call("set_setting", key, enabled);
});

settingsBtn.addEventListener("click", () => {
  if (!state || !state.zalo.installed) return;
  toggleSettings();
});

zaloAction.addEventListener("click", () => {
  if (!state) return;
  if (!state.zalo.installed) {
    call("install_zalo");
    return;
  }
  if (state.accounts.some((account) => account.running)) {
    openModal(
      "Cập nhật Zalo?",
      "Due sẽ tắt Zalo đang mở, cài bản mới, rồi mở lại những tài khoản đang chạy.",
      "Cập nhật và mở lại",
      () => call("update_zalo"),
    );
    return;
  }
  call("update_zalo");
});

modalCancel.addEventListener("click", closeModal);
modalOk.addEventListener("click", () => {
  const action = pendingModal;
  closeModal();
  if (action) action();
});
modal.addEventListener("click", (event) => {
  if (event.target === modal) closeModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (editing || storageId) {
    closePopover();
    return;
  }
  if (!settingsPop.hidden) {
    closeSettings();
    return;
  }
  if (!modal.hidden) closeModal();
});

document.addEventListener("mousedown", (event) => {
  if (!settingsPop.hidden && !event.target.closest("#settings-pop, #settings-btn")) closeSettings();
  if (!editing && !storageId) return;
  if (event.target.closest(".menu-float, .icon-btn[data-action='edit'], .icon-btn[data-action='storage'], .seal")) return;
  closePopover();
});

window.addEventListener("resize", () => {
  const panel = document.querySelector(".menu-float");
  if (!panel) return;
  const anchor = stage.querySelector(`[data-id="${panel.dataset.for}"] .icon-btn.is-on`);
  if (anchor) placeMenu(panel, anchor);
});

window.setMaximized = (enabled) => {
  document.documentElement.classList.toggle("is-maximized", Boolean(enabled));
};

const chromeDrag = document.querySelector(".chrome-drag");
const windowControls = document.querySelector(".window-controls");
if (chromeDrag) {
  chromeDrag.addEventListener("dblclick", () => {
    if (!preview && window.pywebview) window.pywebview.api.toggle_maximize();
  });
}
if (windowControls) {
  windowControls.addEventListener("click", (event) => {
    const button = event.target.closest("[data-window]");
    if (!button || preview || !window.pywebview) return;
    const action = button.dataset.window;
    if (action === "min") window.pywebview.api.minimize();
    if (action === "max") window.pywebview.api.toggle_maximize();
    if (action === "close") window.pywebview.api.close_window();
  });
}

if (preview) {
  if (new URLSearchParams(location.search).get("preview") === "desk" || new URLSearchParams(location.search).get("preview") === "update") {
    mock.zalo = {
      installed: true,
      version: "26.9.10",
      latest: new URLSearchParams(location.search).get("preview") === "update" ? "26.9.11" : null,
      updateAvailable: new URLSearchParams(location.search).get("preview") === "update",
    };
    mock.accounts = [
      {
        id: "account-1",
        name: "Tài khoản 1",
        running: true,
        saving: false,
        openWithWindows: true,
        icon: "",
        disk: 8142743192,
        ram: 1446653952,
        idleFor: 120,
        system: 7.9 * 1024 ** 3,
        cache: 190 * 1024 ** 2,
        media: 0,
        other: 844 * 1024,
        zaloLocation: "Windows (C:)",
        path: "data\\profiles\\account-1",
      },
      {
        id: "account-2",
        name: "Tài khoản 2",
        running: false,
        saving: false,
        icon: "",
        disk: 10 * 1024 ** 2,
        ram: 0,
        system: 0,
        cache: 0,
        media: 0,
        other: 0,
        zaloLocation: "Windows (C:)",
        path: "",
      },
    ];
  }
  draw(mock);
} else {
  window.addEventListener("pywebviewready", refresh);
  window.setInterval(refresh, 1500);
}
