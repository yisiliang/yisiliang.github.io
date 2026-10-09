#!/usr/bin/env python3
"""Exercise the fixed NGINX version with a real upstream and independent keys."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Thread
from collections import Counter
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from time import monotonic, sleep
from datetime import datetime, timezone
import argparse, json, signal, socket, subprocess, uuid
from lab import backend

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nginx", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    binary = str(Path(args.nginx).resolve())
    version = subprocess.run([binary, "-v"], capture_output=True, text=True, check=True).stderr.strip()
    if version != "nginx version: nginx/1.28.0":
        raise SystemExit("Expected nginx/1.28.0, got " + version)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    # A fresh prefix avoids reusing any old zone or pid file.
    prefix = out / ("instance-" + uuid.uuid4().hex[:10])
    (prefix / "logs").mkdir(parents=True)
    server, arrivals = backend()
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        front = reserve.getsockname()[1]
    conf = (ROOT / "lab-nginx.conf").read_text().replace("__FRONTEND_PORT__", str(front)).replace("__BACKEND_PORT__", str(server.server_port))
    (prefix / "nginx.conf").write_text(conf)
    command = [binary, "-p", str(prefix) + "/", "-c", "nginx.conf"]
    subprocess.run(command + ["-t"], check=True, capture_output=True)
    result = {"nginx": version, "executed_at_utc": datetime.now(timezone.utc).isoformat(),
              "workers": 2, "scenarios": [], "scope": "local HTTP/1.1; no cluster, HTTP/2 or memory exhaustion test"}
    nginx = None
    try:
        with (prefix / "process.log").open("w") as log:
            nginx = subprocess.Popen(command, stdout=log, stderr=log)
        for _ in range(100):
            if nginx.poll() is not None:
                raise RuntimeError((prefix / "process.log").read_text())
            try:
                with urlopen(f"http://127.0.0.1:{front}/health", timeout=.2) as response:
                    response.read()
                break
            except (URLError, TimeoutError):
                sleep(.02)
        else:
            raise RuntimeError("Local nginx did not become ready")
        for scenario in ["smooth", "immediate", "threshold", "observe", "multi"]:
            key = uuid.uuid4().hex
            barrier = Barrier(7)
            start = monotonic()

            def request(index):
                barrier.wait(timeout=5)
                sent = monotonic()
                url = f"http://127.0.0.1:{front}/{scenario}?key={key}&id={index}"
                try:
                    response = urlopen(url, timeout=5)
                except HTTPError as error:
                    response = error
                with response:
                    response.read()
                    return {"id": index, "code": response.code, "limit": response.headers.get("X-Limit-Status"),
                            "worker": response.headers.get("X-Worker"), "sent_ms": round((sent-start)*1000, 3),
                            "elapsed_ms": round((monotonic()-sent)*1000, 3)}

            with ThreadPoolExecutor(max_workers=7) as pool:
                clients = list(pool.map(request, range(7)))
            upstream = sorted([r for r in arrivals if r["key"] == key], key=lambda r: r["arrival"])
            initial = upstream[0]["arrival"] if upstream else start
            item = {"name": scenario, "counts": dict(Counter(str(r["code"]) for r in clients)),
                    "send_span_ms": round(max(r["sent_ms"] for r in clients)-min(r["sent_ms"] for r in clients), 3),
                    "upstream_relative_ms": [round((r["arrival"]-initial)*1000, 3) for r in upstream],
                    "clients": clients}
            result["scenarios"].append(item)
        nginx.send_signal(signal.SIGQUIT)
        nginx.wait(timeout=10)
        result["access_log"] = [json.loads(line) for line in (prefix / "logs/access.jsonl").read_text().splitlines()]
        (out / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"output": str(out / "results.json"), "scenarios": [
            {k: s[k] for k in ["name", "counts", "send_span_ms", "upstream_relative_ms"]} for s in result["scenarios"]]}, indent=2))
        for s in result["scenarios"]:
            expected = {"200": 7} if s["name"] == "observe" else ({"200": 4, "429": 3} if s["name"] == "multi" else {"200": 6, "429": 1})
            assert s["counts"] == expected, (s["name"], s["counts"], expected)
        observed = {r["limit"] for r in result["scenarios"][3]["clients"]}
        assert {"PASSED", "DELAYED_DRY_RUN", "REJECTED_DRY_RUN"} <= observed, observed
    finally:
        if nginx and nginx.poll() is None:
            nginx.send_signal(signal.SIGQUIT)
            try:
                nginx.wait(timeout=10)
            except subprocess.TimeoutExpired:
                nginx.terminate()
                nginx.wait(timeout=5)
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == "__main__":
    main()
