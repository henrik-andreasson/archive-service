"use strict";

// web front-end for the archive service, uses the json api in /archive/
// all text is set with textContent, never parsed as HTML, file names come from users

const API = "/archive";
// crypto.subtle.digest needs the whole file in memory, larger files are not checked
const HASH_LIMIT = 256 * 1024 * 1024;

let info = null;

function $(id) {
  return document.getElementById(id);
}

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") e.className = value;
    else if (key === "text") e.textContent = value;
    else e.setAttribute(key, value);
  }
  e.append(...children);
  return e;
}

function notice(message) {
  $("notice").textContent = message;
  $("notice").hidden = !message;
}

function formatSize(bytes) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024;
    i++;
  }
  return (i === 0 ? bytes : bytes.toFixed(1)) + " " + units[i];
}

function short(hash) {
  return hash ? hash.slice(0, 12) + "…" : "";
}

function path(...parts) {
  return parts.map(encodeURIComponent).join("/");
}

async function api(url, options) {
  const r = await fetch(API + url, options);
  let data = null;
  try {
    data = await r.json();
  } catch (e) {
    // not json
  }
  if (!r.ok) throw new Error((data && data.message) || r.status + " " + r.statusText);
  return data;
}

async function localSha256(file) {
  if (!window.isSecureContext || !window.crypto || !crypto.subtle) return { skipped: "needs HTTPS" };
  if (file.size > HASH_LIMIT) return { skipped: "file larger than " + formatSize(HASH_LIMIT) };
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return { hash: Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("") };
}

// XMLHttpRequest instead of fetch, fetch can't report upload progress
function store(file, bucket, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", API + "/store/v1");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch (e) {
        // not json
      }
      if (xhr.status === 200 && data) resolve(data);
      else reject(new Error((data && data.message) || "HTTP " + xhr.status));
    };
    xhr.onerror = () => reject(new Error("network error"));
    const form = new FormData();
    form.append("bucket", bucket);
    form.append("file", file);
    xhr.send(form);
  });
}

function copyButton(text) {
  const button = el("button", { type: "button", class: "small", text: "copy" });
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "copied";
    } catch (e) {
      window.prompt("Copy:", text);
    }
  });
  return button;
}

function setStatus(cell, text, kind) {
  cell.replaceChildren(text);
  cell.className = kind;
}

// --- upload ----------------------------------------------------------------

async function uploadFiles(files) {
  const bucket = $("upload-bucket").value;
  const body = $("uploads").tBodies[0];
  $("uploads").hidden = false;

  for (const file of files) {
    const progress = el("progress", { max: "1", value: "0" });
    const status = el("td", {}, progress);
    const uuid = el("td", { class: "mono" });
    const date = el("td");
    const hash = el("td", { class: "mono" });
    const actions = el("td", { class: "actions" });
    body.prepend(el("tr", {}, el("td", { text: file.name }), status, uuid, date, hash, actions));

    if (info.max_upload_mb && file.size > info.max_upload_mb * 1024 * 1024) {
      setStatus(status, "too large, the limit is " + info.max_upload_mb + " MB", "error");
      continue;
    }

    try {
      const [local, data] = await Promise.all([
        localSha256(file),
        store(file, bucket, (p) => (progress.value = p)),
      ]);
      uuid.textContent = data.uuid;
      date.textContent = data.date;
      hash.textContent = short(data.server_hash);
      hash.title = data.server_hash;
      if (local.hash === undefined) {
        setStatus(status, "stored, sha256 not checked (" + local.skipped + ")", "warn");
      } else if (local.hash === data.server_hash) {
        setStatus(status, "stored, sha256 matches", "ok");
      } else {
        setStatus(status, "stored, but the sha256 does NOT match", "error");
      }
      actions.append(copyButton(
        "uuid:" + data.uuid + ";bucket:" + data.bucket + ";date:" + data.date + ";sha256:" + data.server_hash));
    } catch (e) {
      setStatus(status, e.message, "error");
    }
  }

  if ($("browse-bucket").value === bucket) await loadDates();
}

// --- browse ----------------------------------------------------------------

async function loadDates() {
  const select = $("browse-date");
  const keep = select.value;
  const dates = await api("/list/v1/" + path($("browse-bucket").value) + "/");
  dates.sort().reverse();
  select.replaceChildren(...dates.map((d) => el("option", { value: d, text: d })));
  if (dates.includes(keep)) select.value = keep;
  await loadFiles();
}

async function loadFiles() {
  const bucket = $("browse-bucket").value;
  const date = $("browse-date").value;
  // fetch first and replace all rows at once, so the table doesn't flicker empty
  const files = date ? await api("/list/v1/" + path(bucket, date) + "/?details=1") : [];
  files.sort((a, b) => (b.stored || "").localeCompare(a.stored || ""));
  $("browse").tBodies[0].replaceChildren(...files.map((f) => fileRow(bucket, date, f)));

  $("browse").hidden = files.length === 0;
  $("browse-empty").hidden = files.length > 0;
}

function fileRow(bucket, date, f) {
  const hash = el("td", { class: "mono", text: short(f.sha256) });
  if (f.sha256) hash.title = f.sha256;
  const actions = el("td", { class: "actions" });
  const row = el("tr", {},
    el("td", { text: f.name || "(name not known)" }),
    el("td", { text: formatSize(f.size) }),
    el("td", { text: f.stored ? f.stored.slice(11, 19) : "" }),
    el("td", { class: "mono", text: f.uuid }),
    hash,
    actions);

  actions.append(el("a", { href: API + "/get/v1/" + path(bucket, date, f.uuid), text: "get" }));

  const check = el("button", { type: "button", class: "small", text: "hash" });
  check.addEventListener("click", async () => {
    try {
      const data = await api("/hash/v1/" + path(bucket, date, f.uuid));
      hash.textContent = short(data.hash_remote);
      hash.title = data.hash_remote;
      if (f.sha256 && data.hash_remote !== f.sha256) hash.className = "mono error";
      else hash.className = "mono ok";
    } catch (e) {
      notice("hash failed: " + e.message);
    }
  });
  actions.append(check);

  if (info.allow_remove) {
    const remove = el("button", { type: "button", class: "small danger", text: "delete" });
    remove.addEventListener("click", async () => {
      if (!window.confirm("Delete " + (f.name || f.uuid) + " from the archive?")) return;
      try {
        await api("/delete/v1/" + path(bucket, date, f.uuid), { method: "DELETE" });
        await loadDates();
      } catch (e) {
        notice("delete failed: " + e.message);
      }
    });
    actions.append(remove);
  }
  return row;
}

// --- start -----------------------------------------------------------------

function wrap(fn) {
  return (...args) => fn(...args).catch((e) => notice(e.message));
}

async function init() {
  try {
    info = await api("/info/v1");
  } catch (e) {
    notice("Can not reach the archive: " + e.message);
    return;
  }

  $("client").textContent = "client address: " + info.client_address;
  $("limit").textContent = info.max_upload_mb ? "max " + info.max_upload_mb + " MB per file" : "";
  for (const id of ["upload-bucket", "browse-bucket"]) {
    $(id).replaceChildren(...info.buckets.map((b) => el("option", { value: b, text: b })));
  }
  if (!window.isSecureContext) {
    notice("This page is not served over HTTPS, the sha256 of uploads can not be checked in the browser.");
  }

  const input = $("files");
  input.addEventListener("change", wrap(async () => {
    const files = Array.from(input.files);
    input.value = "";
    await uploadFiles(files);
  }));

  const drop = $("drop");
  drop.addEventListener("dragover", (e) => {
    e.preventDefault();
    drop.classList.add("over");
  });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", wrap(async (e) => {
    e.preventDefault();
    drop.classList.remove("over");
    await uploadFiles(Array.from(e.dataTransfer.files));
  }));

  $("browse-bucket").addEventListener("change", wrap(loadDates));
  $("browse-date").addEventListener("change", wrap(loadFiles));
  $("refresh").addEventListener("click", wrap(loadDates));

  await wrap(loadDates)();
}

init();
