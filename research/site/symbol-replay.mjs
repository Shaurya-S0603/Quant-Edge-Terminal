export const START = "2016-11-01";
export const END = "2024-10-31";
export const RULES = {
  trend: "Trend and volatility",
  sma: "Moving-average crossover",
  hold: "Buy and hold",
};

function isDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const stamp = Date.parse(value + "T00:00:00Z");
  return Number.isFinite(stamp) && new Date(stamp).toISOString().slice(0, 10) === value;
}

export function parseSymbols(value) {
  const symbols = [...new Set(value.trim().toUpperCase().split(/[\s,]+/).filter(Boolean))];
  if (!symbols.length || symbols.length > 5 || symbols.some(
    (symbol) => !/^[A-Z0-9][A-Z0-9-]{0,14}(\.NS)?$/.test(symbol)
  )) {
    throw new Error("Enter one to five Yahoo tickers, such as AAPL, BRK-B or INFY.NS.");
  }
  if (symbols.some((symbol) => symbol.endsWith(".NS") !== symbols[0].endsWith(".NS"))) {
    throw new Error("Use US tickers or NSE tickers in a single test so all prices share a currency.");
  }
  return symbols;
}

export function validateWindow(start, end) {
  if (!isDate(start) || !isDate(end) || start < START || end > END || start >= end) {
    throw new Error("Choose an ordered date range inside Nov 1, 2016 through Oct 31, 2024.");
  }
}

function csvCells(line) {
  // Accept ordinary quoted CSV cells (including doubled quotes) and empty values.
  const cells = [];
  let value = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    if (line[i] === '"') {
      if (quoted && line[i + 1] === '"') {
        value += '"';
        i++;
      } else {
        quoted = !quoted;
      }
    } else if (line[i] === "," && !quoted) {
      cells.push(value.trim());
      value = "";
    } else {
      value += line[i];
    }
  }
  if (quoted) throw new Error("A CSV row has an unclosed quote.");
  cells.push(value.trim());
  return cells;
}

export function parseYahooCsv(text, symbol) {
  const lines = text.replace(/^\uFEFF/, "").trim().split(/\r?\n/);
  const headers = csvCells(lines[0]).map((name) => name.toLowerCase());
  const columns = [
    Math.max(headers.indexOf("date"), headers.indexOf("session")),
    headers.indexOf("open"), headers.indexOf("close"), headers.indexOf("adj close"),
  ];
  if (columns.includes(-1) || new Set(headers).size !== headers.length) {
    throw new Error(symbol + " needs unique Date (or session), Open, Close and Adj Close columns.");
  }
  const rows = [];
  for (const line of lines.slice(1)) {
    if (!line.trim()) continue;
    const cells = csvCells(line);
    const [day, open, close, adjusted] = columns.map((index) => cells[index]);
    if (!isDate(day) || day < START || day > END) {
      throw new Error(symbol + " includes an invalid or out-of-development date. Export only Nov 2016–Oct 2024.");
    }
    const [openPrice, closePrice, adjustedPrice] = [open, close, adjusted].map(Number);
    if (![openPrice, closePrice, adjustedPrice].every((price) => Number.isFinite(price) && price > 0)) {
      throw new Error(symbol + " contains a missing or nonpositive price on " + day + ".");
    }
    rows.push({ day, open: openPrice * adjustedPrice / closePrice, close: adjustedPrice });
  }
  return rows;
}

function checkedRows(symbol, rows) {
  const dates = new Map();
  for (const { day, open, close } of rows) {
    if (!isDate(day) || day < START || day > END || dates.has(day)) {
      throw new Error(symbol + " contains a duplicate, invalid, or out-of-development session.");
    }
    if (!Number.isFinite(open) || !Number.isFinite(close) || open <= 0 || close <= 0) {
      throw new Error(symbol + " contains a missing or nonpositive adjusted price on " + day + ".");
    }
    dates.set(day, { open, close });
  }
  return dates;
}

function checkRule(rule) {
  const within = (value, minimum, maximum) => Number.isInteger(value) && value >= minimum && value <= maximum;
  if (!Object.hasOwn(RULES, rule.id)) throw new Error("Choose a supported strategy.");
  if (rule.id === "trend" && (!within(rule.momentum, 5, 250)
      || !Number.isFinite(rule.volatilityCap) || rule.volatilityCap < .05 || rule.volatilityCap > 1)) {
    throw new Error("Use 5–250 momentum sessions and a 5–100% annualized volatility ceiling.");
  }
  if (rule.id === "sma" && (!within(rule.fast, 2, 249) || !within(rule.slow, 3, 250) || rule.fast >= rule.slow)) {
    throw new Error("Use moving averages of 2–250 sessions, with the fast average shorter than the slow one.");
  }
}

const mean = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;

function weight(rule, series, index, anchor) {
  if (rule.id === "hold") return anchor;
  if (rule.id === "sma") {
    return mean(series.slice(index - rule.fast + 1, index + 1))
      > mean(series.slice(index - rule.slow + 1, index + 1)) ? anchor : 0;
  }
  if (series[index] <= series[index - rule.momentum]) return 0;
  const closes = series.slice(index - 20, index + 1);
  const returns = closes.slice(1).map((value, i) => Math.log(value / closes[i]));
  const average = mean(returns);
  const variance = returns.reduce((sum, value) => sum + (value - average) ** 2, 0) / (returns.length - 1);
  const volatility = Math.sqrt(252 * variance);
  return volatility ? anchor * Math.min(1, rule.volatilityCap / volatility) : anchor;
}

function simulate(days, assets, closes, first, rule, costRate) {
  let cash = 100;
  const positions = Array(assets.length).fill(0);
  let pending;
  const equity = [];
  let month;
  let cost = 0;
  let fills = 0;
  for (let i = first; i < days.length; i++) {
    const prices = assets.map((asset) => asset.get(days[i]));
    if (pending) {
      const available = pending.reduce((sum, order, j) => sum + Math.min(0, order) * prices[j].open, 0);
      const requested = pending.reduce((sum, order, j) => sum + Math.max(0, order) * prices[j].open, 0);
      const scale = requested > 0
        ? Math.min(1, Math.max(0, cash - available * (1 - costRate)) / (requested * (1 + costRate))) : 0;
      pending.forEach((order, j) => {
        const filled = order < 0 ? order : order * scale;
        if (Math.abs(filled) < 1e-12) return;
        const notional = filled * prices[j].open;
        const charges = Math.abs(notional) * costRate;
        positions[j] += filled;
        cash -= notional + charges;
        cost += charges;
        fills++;
      });
      if (cash < -1e-8) throw new Error("The simulation attempted to use cash it did not have.");
      cash = Math.max(0, cash);
      pending = undefined;
    }
    const level = positions.reduce((sum, quantity, j) => sum + quantity * prices[j].close, cash);
    equity.push(level);
    const thisMonth = days[i].slice(0, 7);
    if (i === first || (rule.id !== "hold" && month !== thisMonth)) {
      pending = prices.map(({ close }, j) => (
        level * weight(rule, closes[j], i, 1 / assets.length) / close - positions[j]
      ));
    }
    month = thisMonth;
  }

  let peak = 100;
  const drawdown = equity.map((level) => {
    peak = Math.max(peak, level);
    return level / peak - 1;
  });
  const years = (Date.parse(days.at(-1)) - Date.parse(days[first])) / (365.2425 * 86400000);
  return {
    equity, drawdown, cost, fills, totalReturn: equity.at(-1) / 100 - 1,
    cagr: years >= 1 ? (equity.at(-1) / 100) ** (1 / years) - 1 : null,
    maxDrawdown: Math.min(...drawdown),
  };
}

export function runReplay(symbols, histories, { start, end, rule, costsBps }) {
  symbols = parseSymbols(symbols.join(" "));
  validateWindow(start, end);
  checkRule(rule);
  if (!Number.isFinite(costsBps) || costsBps < 0 || costsBps > 500) {
    throw new Error("Set total fees and slippage to 0–500 basis points per side.");
  }
  const assets = symbols.map((symbol) => checkedRows(symbol, histories[symbol] || []));
  const allDays = [...new Set(assets.flatMap((asset) => [...asset.keys()]))].sort();
  const dates = allDays.filter((day) => day <= end && assets.every((asset) => asset.has(day)));
  const lookback = rule.id === "trend" ? Math.max(rule.momentum, 20) + 1 : rule.id === "sma" ? rule.slow : 1;
  const first = dates.findIndex((day, i) => day >= start && i + 1 >= lookback);
  if (first === -1 || dates.length <= first + 1) {
    throw new Error("Too few shared dates after warm-up to trade. Use older history, a wider window or a shorter lookback.");
  }
  const closes = assets.map((asset) => dates.map((day) => asset.get(day).close));
  const notices = [];
  assets.forEach((asset, i) => {
    const rows = [...asset.entries()].sort(([a], [b]) => a.localeCompare(b));
    const anomalous = rows.find(([day, price], j) => day <= end && j
      && Math.abs(price.close / rows[j - 1][1].close - 1) > .4);
    if (anomalous) notices.push(symbols[i] + " moved over 40% on " + anomalous[0] + ". Check corporate actions before interpreting the result.");
  });
  return {
    dates: dates.slice(first),
    excluded: allDays.filter((day) => start <= day && day <= end).length
      - dates.filter((day) => start <= day).length,
    notices,
    net: simulate(dates, assets, closes, first, rule, costsBps / 10000),
    gross: simulate(dates, assets, closes, first, rule, 0),
    benchmark: simulate(dates, assets, closes, first, { id: "hold" }, costsBps / 10000),
  };
}
