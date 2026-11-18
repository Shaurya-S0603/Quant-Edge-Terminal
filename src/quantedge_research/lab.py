"""Serve Strategy Lab locally or export a Yahoo snapshot for the hosted tester."""

from argparse import ArgumentParser
from datetime import date
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from threading import BoundedSemaphore
from urllib.parse import parse_qs, urlsplit

from .data import Instrument
from .historical_strategy import adjusted_prices
from .yahoo import fetch_provider_history

START = date(2016, 11, 1)
END_EXCLUSIVE = date(2024, 11, 1)
SYMBOL_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9-]{0,14}(?:\.NS)?")
PROJECT = Path(__file__).resolve().parents[2]
SITE = PROJECT / "research" / "site"
CACHE = PROJECT / ".data" / "research" / "lab-yahoo-cache"
ASSETS = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/style.css": ("style.css", "text/css"),
    "/app.js": ("app.js", "text/javascript"),
    "/tester.mjs": ("tester.mjs", "text/javascript"),
    "/symbol-replay.mjs": ("symbol-replay.mjs", "text/javascript"),
    "/report.json": ("report.json", "application/json"),
}
PROVIDER_SLOTS = BoundedSemaphore(2)


def instrument_for(symbol: str) -> Instrument:
    ticker = symbol.strip().upper()
    if SYMBOL_PATTERN.fullmatch(ticker) is None:
        raise ValueError("Use a US ticker such as BRK-B or an NSE ticker such as INFY.NS.")
    market, currency = ("NSE", "INR") if ticker.endswith(".NS") else ("US", "USD")
    return Instrument(f"{market.lower()}:{ticker}", ticker, market, currency)


@lru_cache(maxsize=32)
def provider_rows(ticker: str) -> tuple[dict, ...]:
    instrument = instrument_for(ticker)
    if not PROVIDER_SLOTS.acquire(timeout=40):
        raise TimeoutError("Yahoo history is busy. Retry in a moment.")
    try:
        frame = fetch_provider_history(instrument, START, END_EXCLUSIVE, CACHE)
    finally:
        PROVIDER_SLOTS.release()
    prices, _ = adjusted_prices(
        frame, START, END_EXCLUSIVE, ticker=ticker, reject_outliers=False,
    )
    return tuple(
        {"day": day.isoformat(), "open": bar.open, "close": bar.close}
        for day, bar in prices.items()
    )


class LabHandler(BaseHTTPRequestHandler):
    def send_payload(self, status: HTTPStatus, content_type: str, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def send_json(self, status: HTTPStatus, body: dict) -> None:
        self.send_payload(status, "application/json", json.dumps(body, allow_nan=False).encode())

    def do_GET(self) -> None:
        port = self.server.server_address[1]
        if self.headers.get("Host") not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "Open the printed localhost address."})
            return
        request = urlsplit(self.path)
        if request.path == "/api/status":
            self.send_json(HTTPStatus.OK, {"yahoo": True})
            return
        if request.path == "/api/history":
            self.history(request.query)
            return
        if request.path in ASSETS:
            filename, content_type = ASSETS[request.path]
            try:
                payload = (SITE / filename).read_bytes()
            except FileNotFoundError:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "Lab asset is missing."})
            else:
                self.send_payload(HTTPStatus.OK, content_type, payload)
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "Page not found."})

    def do_HEAD(self) -> None:
        if self.path.startswith("/api/history"):
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.end_headers()
            return
        self.do_GET()

    def history(self, query: str) -> None:
        try:
            params = parse_qs(query, strict_parsing=True, max_num_fields=1)
            if set(params) != {"symbol"} or len(params["symbol"]) != 1:
                raise ValueError("Supply exactly one symbol.")
            instrument = instrument_for(params["symbol"][0])
        except ValueError as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        try:
            rows = provider_rows(instrument.ticker)
        except Exception as error:
            self.log_error("Yahoo history for %s failed: %s", instrument.ticker, type(error).__name__)
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "error": f"Yahoo history is unavailable for {instrument.ticker}. Check the ticker or select a CSV.",
            })
            return
        self.send_json(HTTPStatus.OK, {"symbol": instrument.ticker, "currency": instrument.currency, "rows": rows})


def export_csv(symbols: list[str], output: Path) -> None:
    instruments = tuple(dict.fromkeys(instrument_for(symbol) for symbol in symbols))
    output.mkdir(parents=True, exist_ok=True)
    for instrument in instruments:
        path = output / f"{instrument.ticker}.csv"
        frame = fetch_provider_history(instrument, START, END_EXCLUSIVE, CACHE)
        adjusted_prices(
            frame, START, END_EXCLUSIVE, ticker=instrument.ticker, reject_outliers=False,
        )
        partial = path.with_suffix(".csv.tmp")
        frame.to_csv(partial, index=False)
        partial.replace(path)
        print(path)


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="command", required=True)
    server = actions.add_parser("serve", help="Run the lab and Yahoo adapter on localhost")
    server.add_argument("--port", type=int, default=8765)
    exporter = actions.add_parser("export", help="Save Yahoo histories as separate ticker CSVs")
    exporter.add_argument("symbols", nargs="+")
    exporter.add_argument("--output", type=Path, default=PROJECT / ".data" / "exports")
    args = parser.parse_args()
    if args.command == "export":
        export_csv(args.symbols, args.output)
        return
    with ThreadingHTTPServer(("127.0.0.1", args.port), LabHandler) as httpd:
        print(f"QuantEdge Strategy Lab at http://127.0.0.1:{httpd.server_port}", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
