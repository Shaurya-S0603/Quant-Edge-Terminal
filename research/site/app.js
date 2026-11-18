const byId = (id) => document.getElementById(id);
const colors = { net: "#52e6ca", gross: "#ba9afa", fixed: "#edc57a", benchmark: "#78aaff" };
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const percent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });
const dateFormat = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeZone: "UTC" });
const dateText = (date) => dateFormat.format(new Date(date + "T00:00:00Z"));
const svgNamespace = "http://www.w3.org/2000/svg";
let data;
let market = "US";
let view = "equity";

function svgNode(name, attrs, parent) {
  const node = document.createElementNS(svgNamespace, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  parent.append(node);
  return node;
}

function textNode(name, content, parent, className) {
  const node = document.createElement(name);
  node.textContent = content;
  if (className) node.className = className;
  parent.append(node);
  return node;
}

function gridInterval(span, ticks) {
  const approximate = span / ticks;
  const unit = 10 ** Math.floor(Math.log10(approximate));
  return ([1, 2, 2.5, 5, 10].find((step) => step * unit >= approximate) || 10) * unit;
}

function draw(id, { label, labels, lines, bands = [], mode }) {
  const holder = byId(id);
  const width = Math.max(240, holder.clientWidth);
  const height = 282;
  const left = mode === "drawdown" ? 48 : 43;
  const right = width - 13;
  const top = 17;
  const bottom = height - 31;
  const count = labels.length;
  const extents = lines.flatMap(({ values }) => values).concat(bands.flatMap(({ low, high }) => low.concat(high)));
  const minimum = Math.min(...extents);
  const maximum = Math.max(...extents);
  const tick = gridInterval(Math.max(maximum - minimum, 1), 5);
  const low = Math.floor(minimum / tick) * tick;
  const high = Math.max(low + tick, Math.ceil(maximum / tick) * tick);
  const x = (i) => left + i * (right - left) / (count - 1);
  const y = (value) => bottom - (value - low) * (bottom - top) / (high - low);
  const format = mode === "drawdown" ? (value) => percent.format(value / 100) : (value) => number.format(value);
  const coordinates = (values) => values.map((value, i) => [x(i).toFixed(2), y(value).toFixed(2)]);
  const pathOf = (points) => points.map(([px, py], i) => (i ? "L" : "M") + px + "," + py).join(" ");
  holder.replaceChildren();
  const svg = svgNode("svg", { viewBox: "0 0 " + width + " " + height, role: "img", "aria-label": label }, holder);

  for (let index = 0; index <= Math.round((high - low) / tick); index++) {
    const value = low + index * tick;
    const plotY = y(value);
    const isBase = value === (mode === "drawdown" ? 0 : 100);
    svgNode("line", { x1: left, y1: plotY, x2: right, y2: plotY, class: isBase ? "chart-zero" : "chart-grid-line" }, svg);
    svgNode("text", { x: left - 7, y: plotY + 4, class: "tick", "text-anchor": "end" }, svg).textContent = format(value);
  }

  if (mode === "simulation" && low < 100 && high > 100 && (100 - low) % tick !== 0) {
    svgNode("line", { x1: left, y1: y(100), x2: right, y2: y(100), class: "chart-zero" }, svg);
  }
  const divisions = width >= 580 ? 5 : 4;
  for (let i = 0; i <= divisions; i++) {
    const index = Math.round((count - 1) * i / divisions);
    const anchor = i === 0 ? "start" : i === divisions ? "end" : "middle";
    const text = mode === "simulation" ? labels[index] : labels[index].slice(0, 4);
    svgNode("text", { x: x(index), y: bottom + 20, class: "tick", "text-anchor": anchor }, svg).textContent = text;
  }

  for (const band of bands) {
    const boundary = coordinates(band.high).concat(coordinates(band.low).reverse());
    svgNode("path", { d: pathOf(boundary) + " Z", fill: band.fill }, svg);
  }
  for (const line of lines) {
    svgNode("path", {
      d: pathOf(coordinates(line.values)), fill: "none", stroke: colors[line.key],
      "stroke-width": line.key === "net" ? 2.15 : 1.35,
      "stroke-dasharray": line.key === "benchmark" || line.key === "gross" ? "5 4" : "none",
      "stroke-linejoin": "round",
    }, svg);
  }

  const cross = svgNode("line", { y1: top, y2: bottom, class: "crosshair", visibility: "hidden" }, svg);
  const dots = lines.map((line) => svgNode("circle", {
    r: line.key === "net" ? 3.6 : 2.4, fill: colors[line.key], visibility: "hidden",
  }, svg));
  const tooltip = textNode("div", "", holder, "tooltip");
  tooltip.hidden = true;
  tooltip.setAttribute("aria-hidden", "true");

  function highlight(index) {
    const cursor = x(index);
    cross.setAttribute("x1", cursor);
    cross.setAttribute("x2", cursor);
    cross.setAttribute("visibility", "visible");
    tooltip.replaceChildren();
    tooltip.style.left = cursor < width / 2 ? Math.min(cursor + 9, width - 143) + "px" : "auto";
    tooltip.style.right = cursor < width / 2 ? "auto" : (width - cursor + 8) + "px";
    textNode("strong", mode === "simulation" ? "Session " + labels[index] : dateText(labels[index]), tooltip);
    for (const [i, line] of lines.entries()) {
      const row = textNode("div", "", tooltip);
      textNode("span", line.label, row);
      const value = textNode("b", format(line.values[index]), row);
      value.style.color = colors[line.key];
      dots[i].setAttribute("cx", cursor);
      dots[i].setAttribute("cy", y(line.values[index]));
      dots[i].setAttribute("visibility", "visible");
    }
    if (bands.length) {
      const row = textNode("div", "", tooltip);
      textNode("span", "5th–95th", row);
      textNode("b", format(bands[0].low[index]) + "–" + format(bands[0].high[index]), row);
    }
    tooltip.hidden = false;
  }

  svg.addEventListener("pointermove", (event) => {
    const local = event.clientX - svg.getBoundingClientRect().left;
    highlight(Math.max(0, Math.min(count - 1, Math.round((local - left) / (right - left) * (count - 1)))));
  });
  svg.addEventListener("pointerleave", () => {
    tooltip.hidden = true;
    cross.setAttribute("visibility", "hidden");
    for (const dot of dots) dot.setAttribute("visibility", "hidden");
  });
}

function addTableRow(target, label, values, primary = false) {
  const row = document.createElement("tr");
  if (primary) row.className = "primary";
  textNode("th", label, row).scope = "row";
  for (const value of values) textNode("td", value, row);
  target.append(row);
}

function historicalLines(portfolio) {
  const labels = { net: "Strategy net", gross: "Strategy gross", fixed: "Fixed basket", benchmark: portfolio.benchmark };
  return Object.entries(labels).filter(([key]) => portfolio.equity[key]).map(([key, label]) => {
    let peak = 100;
    const values = portfolio.equity[key].map((value) => {
      peak = Math.max(peak, value);
      return view === "drawdown" ? 100 * (value / peak - 1) : value;
    });
    return { key, label, values };
  });
}

function renderHistorical() {
  const portfolio = data.markets[market];
  const lines = historicalLines(portfolio);
  byId("equity-title").textContent = view === "drawdown" ? "Drawdown from peak" : "Equity curve";
  byId("scoring").textContent = view === "drawdown"
    ? "Daily percentage below each portfolio’s prior peak" : "Growth of 100 · " + portfolio.currency;
  const legend = byId("historical-legend");
  legend.replaceChildren();
  for (const line of lines) {
    const entry = textNode("span", "", legend);
    textNode("i", "", entry, "line " + line.key);
    entry.append(line.label);
  }
  draw("historical-plot", {
    label: byId("equity-title").textContent + " for " + (market === "US" ? "US equities" : "Indian equities"),
    labels: portfolio.equity.dates,
    lines,
    mode: view,
  });
}

function renderSimulation() {
  const scenario = data.markets[market].bootstrap[byId("block").value];
  const { p05, p25, p50, p75, p95 } = scenario.bands;
  draw("simulation-plot", {
    label: "Distribution of simulated wealth using " + scenario.block + "-session blocks",
    labels: Array.from({ length: scenario.steps + 1 }, (_, i) => String(i)),
    lines: [
      { key: "fixed", label: "Basket median", values: scenario.fixed_median },
      { key: "net", label: "Strategy median", values: p50 },
    ],
    bands: [
      { low: p05, high: p95, fill: "#204a9c85" },
      { low: p25, high: p75, fill: "#3978e68c" },
    ],
    mode: "simulation",
  });
  byId("scenario").textContent = "With " + scenario.block + "-session blocks, the middle 90% of simulated year-end strategy values ran from "
    + number.format(p05.at(-1)) + " to " + number.format(p95.at(-1)) + " starting from 100. "
    + percent.format(scenario.fraction_below_start) + " of paths ended below 100 and "
    + percent.format(scenario.fraction_beating_fixed) + " finished ahead of the paired fixed basket.";
}

function renderMarket() {
  const portfolio = data.markets[market];
  const coverage = portfolio.coverage;
  const metrics = portfolio.metrics;
  const net = metrics.net;
  const fixed = metrics.fixed;
  byId("coverage").textContent = coverage.sessions_used.toLocaleString("en-US") + " of "
    + coverage.sessions_expected.toLocaleString("en-US") + " sessions · "
    + portfolio.instrument_count + " stocks · Yahoo Finance";
  const cards = [
    ["Net CAGR", percent.format(net.cagr), percent.format(fixed.cagr) + " fixed basket"],
    ["Maximum drawdown", percent.format(-net.max_drawdown), percent.format(-fixed.max_drawdown) + " fixed basket"],
    ["Net Sharpe", net.sharpe.toFixed(2), fixed.sharpe.toFixed(2) + " fixed basket"],
    ["Average cash", percent.format(net.mean_cash_weight), "Daily closing balance"],
  ];
  const stats = byId("stats");
  stats.replaceChildren();
  for (const [label, value, footnote] of cards) {
    const card = textNode("div", "", stats, "stat");
    textNode("span", label, card, "stat-label");
    textNode("strong", value, card);
    textNode("small", footnote, card);
  }
  const performance = byId("performance");
  performance.replaceChildren();
  for (const line of historicalLines(portfolio)) {
    const row = metrics[line.key];
    addTableRow(performance, line.label, [
      percent.format(row.cagr), percent.format(row.volatility),
      percent.format(-row.max_drawdown), row.sharpe.toFixed(2),
    ], line.key === "net");
  }
  const folds = byId("folds");
  folds.replaceChildren();
  for (const fold of portfolio.folds) {
    addTableRow(folds, dateText(fold.start), ["fixed_rule", "walk_forward", "fixed_weights"]
      .map((key) => percent.format(fold[key])));
  }
  const note = byId("benchmark-note");
  note.hidden = !portfolio.split_basis_corrections.length;
  note.textContent = note.hidden ? "" : "Nifty BeES price units reconciled to NSE records on Dec 19 and 20, 2019.";
  byId("finding").textContent = "The strategy reduced maximum drawdown by "
    + number.format((fixed.max_drawdown - net.max_drawdown) * 100)
    + " percentage points versus the same-stock monthly basket. It held "
    + percent.format(net.mean_cash_weight) + " in cash on average and trailed the basket in net annualized return and Sharpe.";
  renderHistorical();
  renderSimulation();
}

function activate(container, property, callback) {
  for (const button of container.querySelectorAll("button")) {
    button.addEventListener("click", () => {
      if (button.getAttribute("aria-pressed") === "true") return;
      container.querySelector('[aria-pressed="true"]').setAttribute("aria-pressed", "false");
      button.setAttribute("aria-pressed", "true");
      callback(button.dataset[property]);
    });
  }
}

async function start() {
  try {
    const response = await fetch("report.json");
    if (!response.ok) throw new Error("Historical dataset unavailable.");
    data = await response.json();
    byId("report").hidden = false;
    renderMarket();
  } catch (error) {
    byId("report").hidden = true;
    byId("error").hidden = false;
    byId("error").textContent = "The historical report couldn’t load. Refresh the page to retry.";
    byId("coverage").textContent = "Report unavailable";
    console.error(error);
    return;
  }
  activate(byId("markets"), "market", (selection) => { market = selection; renderMarket(); });
  activate(byId("views"), "view", (selection) => { view = selection; renderHistorical(); });
  byId("block").addEventListener("change", renderSimulation);
  let previousWidth = 0;
  new ResizeObserver(([entry]) => {
    const width = Math.round(entry.contentRect.width);
    if (width !== previousWidth) {
      previousWidth = width;
      renderHistorical();
      renderSimulation();
    }
  }).observe(byId("report"));
}

start();
