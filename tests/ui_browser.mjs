// drives headless Chrome/Chromium over the DevTools protocol for tests/test_ui_browser.py
//
//   node tests/ui_browser.mjs <chrome> <page url> <file to upload> [screenshot.png]
//
// loads the page, uploads a file through the file input, deletes it again
// through the page and prints the results as json

import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const [chrome, url, uploadFile, screenshot] = process.argv.slice(2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const result = { problems: [] };

// always print a json result, also if something unexpected fails
function finish(code = 0) {
  console.log(JSON.stringify(result));
  process.exit(code);
}
process.on("uncaughtException", (e) => {
  result.error = "uncaught: " + (e.stack || e);
  finish();
});

const profile = fs.mkdtempSync(path.join(os.tmpdir(), "archive-ui-chrome-"));
const browser = spawn(chrome, [
  "--headless=new", "--no-first-run", "--no-default-browser-check", "--disable-gpu",
  "--disable-dev-shm-usage", "--no-sandbox", "--remote-debugging-port=0",
  "--user-data-dir=" + profile, "about:blank",
], { stdio: ["ignore", "ignore", "pipe"], detached: true });

// keep the end of chrome's output to explain a failed start
let browserLog = "";
let browserExit = null;
browser.stderr.on("data", (d) => (browserLog = (browserLog + d).slice(-2000)));
browser.on("error", (e) => (browserExit = "can not start " + chrome + ": " + e.message));
browser.on("exit", (code, signal) => (browserExit = browserExit || `${chrome} exited (code ${code}, signal ${signal})`));

async function waitFor(check, what, timeout = 20000) {
  result.step = what;
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    if (browserExit) throw new Error(browserExit);
    const value = await check();
    if (value) return value;
    await sleep(100);
  }
  throw new Error("timeout waiting for " + what);
}
try {
  // chrome writes the port it picked to DevToolsActivePort
  const port = await waitFor(() => {
    try {
      return fs.readFileSync(path.join(profile, "DevToolsActivePort"), "utf8").split("\n")[0];
    } catch {
      return null;
    }
  }, "chrome");
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((r, e) => { ws.onopen = r; ws.onerror = e; });

  let id = 0;
  const pending = new Map();
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
    const p = msg.params;
    if (msg.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(p.type)) {
      result.problems.push("console: " + p.args.map((a) => a.value ?? a.description).join(" "));
    } else if (msg.method === "Runtime.exceptionThrown") {
      result.problems.push("exception: " + (p.exceptionDetails.exception?.description ?? p.exceptionDetails.text));
    } else if (msg.method === "Log.entryAdded" && p.entry.level === "error") {
      result.problems.push("log: " + p.entry.text);
    } else if (msg.method === "Page.javascriptDialogOpening") {
      result.dialog = p.message;
      send("Page.handleJavaScriptDialog", { accept: true });
    }
  };
  const send = (method, params = {}) => new Promise((r) => {
    const i = ++id;
    pending.set(i, r);
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  const js = async (expression) =>
    (await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result.result?.value;
  const rows = (table) => js(`[...document.querySelectorAll('#${table} tbody tr')]
    .map(r => [...r.cells].map(c => c.textContent))`);

  for (const domain of ["Page", "Runtime", "Log", "DOM"]) await send(domain + ".enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 1200, height: 800, deviceScaleFactor: 1, mobile: false });
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] });
  await send("Page.navigate", { url });
  await waitFor(() => js("document.getElementById('client').textContent !== ''"), "page start");
  await sleep(500);

  result.secure_context = await js("window.isSecureContext");
  result.client = await js("document.getElementById('client').textContent");
  result.buckets = await js("[...document.getElementById('upload-bucket').options].map(o => o.value)");
  await waitFor(async () => (await rows("browse")).length > 0, "file list");
  result.browse_before = await rows("browse");
  result.html_elements_in_names = await js("document.querySelectorAll('#browse td img, #browse td script').length");

  // upload through the file input
  const doc = await send("DOM.getDocument");
  const input = await send("DOM.querySelector", { nodeId: doc.result.root.nodeId, selector: "#files" });
  await send("DOM.setFileInputFiles", { nodeId: input.result.nodeId, files: [uploadFile] });
  await waitFor(async () => (await rows("uploads"))?.[0]?.[1]?.startsWith("stored"), "upload");
  result.upload = (await rows("uploads"))[0];
  const name = path.basename(uploadFile);
  await waitFor(async () => (await rows("browse")).some((r) => r[0] === name), "file in list");
  result.browse_after_upload = await rows("browse");

  if (screenshot) {
    const png = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(screenshot, Buffer.from(png.result.data, "base64"));
  }

  // delete it through the page, the confirm dialog is accepted
  await js(`[...document.querySelectorAll('#browse tbody tr')]
    .find(r => r.cells[0].textContent === ${JSON.stringify(name)})
    .querySelector('button.danger').click()`);
  // wait for the reloaded list: not empty and without the deleted file
  await waitFor(async () => {
    const list = await rows("browse");
    return list.length > 0 && !list.some((r) => r[0] === name);
  }, "delete");
  result.browse_after_delete = await rows("browse");
  ws.close();
} catch (e) {
  result.error = String(e);
  result.browser_log = browserLog;
} finally {
  // chrome keeps writing to its profile while it stops, wait for it to exit
  // before removing the profile, and never fail the test on the cleanup
  // stop chrome and its helper processes (own process group, detached)
  if (browserExit === null) {
    const exited = new Promise((r) => browser.once("exit", r));
    try {
      process.kill(-browser.pid, "SIGTERM");
    } catch {
      browser.kill();
    }
    await Promise.race([exited, sleep(5000)]);
  }
  try {
    process.kill(-browser.pid, "SIGKILL");
  } catch {
    // all gone
  }
  try {
    fs.rmSync(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
  } catch (e) {
    console.error("could not remove " + profile + ": " + e.message);
  }
}
finish();
