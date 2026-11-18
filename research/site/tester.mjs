import { draw } from "./app.js";
import { parseSymbols, parseYahooCsv, RULES, runReplay, validateWindow } from "./symbol-replay.mjs";

const byId = (id) => document.getElementById(id);
const dateFormat = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeZone: "UTC" });
const dateText = (day) => dateFormat.format(new Date(day + "T00:00:00Z"));
const percent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 2 });
const baseUrl = new URL(".", import.meta.url);
const localYahoo = ["localhost", "127.0.0.1"].includes(baseUrl.hostname)
  ? fetch(new URL("api/status", baseUrl)).then(async (response) => (
    response.ok && (await response.json()).yahoo === true
  )).catch(() => false)
  : Promise.resolve(false);
const title = byId("test-result-title");
const fileInput = byId("test-files");
let report;
let view = "equity";

function currentRule() {
  const id = byId("test-rule").value;
  if (id === "trend") return {
    id, momentum: byId("momentum").valueAsNumber, volatilityCap: byId("volatility-cap").valueAsNumber / 100,
  };
  if (id === "sma") return { id, fast: byId("sma-fast").valueAsNumber, slow: byId("sma-slow").valueAsNumber };
  return { id };
}

async function localHistory(symbol) {
  const url = new URL("api/history", baseUrl);
  url.searchParams.set("symbol", symbol);
  const response = await fetch(url, { signal: AbortSignal.timeout(55000) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Yahoo history is unavailable for " + symbol + ".");
  return result.rows;
}

async function historiesFor(symbols) {
  const files = [...fileInput.files];
  if (!files.length) {
    if (!await localYahoo) throw new Error("Choose one daily price CSV per ticker to run a test on this Site.");
    byId("test-state").textContent = "Fetching historical bars from Yahoo Finance…";
    return Object.fromEntries(await Promise.all(symbols.map(async (symbol) => [symbol, await localHistory(symbol)])));
  }
  const names = new Map(files.map((file) => [file.name.toUpperCase(), file]));
  if (names.size !== files.length || names.size !== symbols.length) {
    throw new Error("Provide exactly one named CSV per symbol.");
  }
  const entries = await Promise.all(symbols.map(async (symbol) => {
    const file = names.get(symbol + ".CSV");
    if (!file || file.size > 2_000_000) throw new Error("Choose " + symbol + ".csv (up to 2 MB).");
    return [symbol, parseYahooCsv(await file.text(), symbol)];
  }));
  return Object.fromEntries(entries);
}

function showChart() {
  if (!report) return;
  draw("custom-plot", {
    label: view === "equity" ? "Portfolio growth from 100" : "Portfolio drawdown from peak",
    labels: report.dates,
    mode: view,
    lines: [
      { key: "fixed", label: "Buy and hold net", run: report.benchmark },
      { key: "gross", label: "Strategy gross", run: report.gross },
      { key: "net", label: "Strategy net", run: report.net },
    ].map(({ key, label, run }) => ({
      key, label, values: view === "equity" ? run.equity : run.drawdown.map((value) => value * 100),
    })),
  });
}

function showReport(result, symbols, rule) {
  report = result;
  title.textContent = RULES[rule.id] + " / " + symbols.join(", ");
  byId("test-result-scope").textContent = dateText(report.dates[0]) + " – " + dateText(report.dates.at(-1))
    + " · " + report.dates.length.toLocaleString("en-US") + " shared sessions"
    + " · " + (symbols[0].endsWith(".NS") ? "INR" : "USD");
  byId("test-notes").textContent = (report.excluded
    ? report.excluded + " dates present for only part of the basket were excluded. " : "")
    + report.notices.join(" ");
  const table = byId("custom-metrics");
  table.replaceChildren();
  for (const [label, row] of [
    ["Strategy net", report.net], ["Strategy gross", report.gross], ["Buy and hold net", report.benchmark],
  ]) {
    const tr = document.createElement("tr");
    const heading = document.createElement("th");
    heading.scope = "row";
    heading.textContent = label;
    if (row === report.net) tr.className = "primary";
    tr.append(heading);
    for (const value of [percent.format(row.totalReturn), row.cagr === null ? "—" : percent.format(row.cagr),
      percent.format(row.maxDrawdown), row.fills.toLocaleString("en-US")]) {
      const td = document.createElement("td");
      td.textContent = value;
      tr.append(td);
    }
    table.append(tr);
  }
  byId("test-result").hidden = false;
  showChart();
}

byId("test-rule").addEventListener("change", ({ target }) => {
  for (const wrapper of document.querySelectorAll("[data-rule-options]")) {
    wrapper.hidden = wrapper.dataset.ruleOptions !== target.value;
    wrapper.querySelector("input").disabled = wrapper.hidden;
  }
});

byId("test-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = byId("test-error");
  const button = byId("run-test");
  if (button.disabled) return;
  button.disabled = true;
  error.hidden = true;
  report = undefined;
  byId("test-result").hidden = true;
  byId("test-state").textContent = "Preparing historical data…";
  try {
    const symbols = parseSymbols(byId("symbols").value);
    const start = byId("test-from").value;
    const end = byId("test-to").value;
    validateWindow(start, end);
    const rule = currentRule();
    const costsBps = byId("test-cost").valueAsNumber;
    const histories = await historiesFor(symbols);
    showReport(runReplay(symbols, histories, { start, end, rule, costsBps }), symbols, rule);
    byId("test-state").textContent = "Historical test complete.";
  } catch (reason) {
    error.textContent = reason.message;
    error.hidden = false;
    byId("test-state").textContent = "";
  } finally {
    button.disabled = false;
  }
});

for (const button of byId("custom-views").querySelectorAll("button")) {
  button.addEventListener("click", () => {
    byId("custom-views").querySelector('[aria-pressed="true"]').setAttribute("aria-pressed", "false");
    button.setAttribute("aria-pressed", "true");
    view = button.dataset.customView;
    showChart();
  });
}

let previousWidth;
new ResizeObserver(([entry]) => {
  const width = Math.round(entry.contentRect.width);
  if (width && width !== previousWidth) {
    previousWidth = width;
    showChart();
  }
}).observe(byId("test-result"));

localYahoo.then((available) => {
  if (available) {
    byId("source-help").textContent = "Yahoo Finance fetches historical prices when no CSVs are selected. CSVs are processed in your browser.";
  }
});
