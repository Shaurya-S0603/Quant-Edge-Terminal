import assert from "node:assert/strict";
import { test } from "node:test";

import { parseSymbols, parseYahooCsv, runReplay } from "../site/symbol-replay.mjs";

const start = "2020-01-02";
const end = "2020-02-03";
const hold = { id: "hold" };
const price = (day, open, close) => ({ day, open, close });

test("ticker changes deduplicate input and keep market currency consistent", () => {
  assert.deepEqual(parseSymbols(" aapl, MSFT AAPL "), ["AAPL", "MSFT"]);
  assert.deepEqual(parseSymbols("infy.ns\nTCS.NS"), ["INFY.NS", "TCS.NS"]);
  assert.throws(() => parseSymbols("INFY.NS AAPL"), /single test/);
  assert.throws(() => parseSymbols("AAPL/../MSFT"), /one to five/);
});

test("CSV dates are checked before parsing holdout prices", () => {
  const header = '\uFEFF"Date",Open,Close,"Adj Close"\r\n';
  assert.deepEqual(parseYahooCsv(header + "2024-10-31,100,110,55", "AAPL"), [price("2024-10-31", 50, 55)]);
  assert.throws(() => parseYahooCsv(header + "2024-11-01,abc,abc,abc", "AAPL"), /out-of-development/);
  assert.throws(() => parseYahooCsv(header + "2024-10-31,101,-100,50", "AAPL"), /nonpositive/);
  assert.throws(() => runReplay(["AAPL"], {}, { start, end: "2024-11-01", rule: hold, costsBps: 0 }), /date range/);
});

test("buy and hold waits until the next open and pays each fill cost", () => {
  const rows = [price(start, 45, 50), price("2020-01-03", 100, 100), price(end, 100, 80)];
  const replay = runReplay(["AAPL"], { AAPL: rows }, { start, end, rule: hold, costsBps: 100 });
  assert.deepEqual(replay.gross.equity, [100, 100, 80]);
  assert.equal(replay.net.equity[0], 100);
  assert.ok(Math.abs(replay.net.equity[1] - 100 / 1.01) < 1e-9);
  assert.equal(replay.net.fills, 1);
  assert.deepEqual(replay.net, replay.benchmark);
  assert.equal(replay.gross.maxDrawdown, -0.19999999999999996);
});

test("moving-average decisions use completed closes and omit unshared dates", () => {
  const days = ["2019-12-30", "2019-12-31", start, "2020-01-03", "2020-01-06", end];
  const ascend = [80, 90, 100, 220, 200, 10];
  const rows = days.map((day, i) => price(day, ascend[i], ascend[i]));
  const rule = { id: "sma", fast: 2, slow: 3 };
  const cfg = { start, end, rule, costsBps: 0 };
  const result = runReplay(["AAPL", "MSFT"], { AAPL: rows, MSFT: rows.filter((_, i) => i !== 4) }, cfg);
  const changed = runReplay(["AAPL", "MSFT"], {
    AAPL: rows.map((row, i) => i === 5 ? price(row.day, 500, 500) : row),
    MSFT: rows.filter((_, i) => i !== 4),
  }, cfg);
  assert.deepEqual(result.dates, [start, "2020-01-03", end]);
  assert.equal(result.excluded, 1);
  assert.deepEqual(result.net.equity.slice(0, 2), [100, 100]);
  assert.deepEqual(changed.net.equity.slice(0, 2), result.net.equity.slice(0, 2));
  // The ledgers buy both names one session after the signal.
  assert.equal(result.net.fills, 2);
});
