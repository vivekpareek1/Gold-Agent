"""
Public read-only dashboard for the gold trading agent, PLUS two protected
admin endpoints used because Render's free tier has no cron job support:

  GET /run-check?token=...      -- runs one live_check cycle (fast, synchronous)
  GET /run-backtest?token=...   -- kicks off the 1-month LLM backtest in a
                                    background thread (slow, ~20-30 min);
                                    progress is visible on the Backtest tab
                                    as trades get inserted in real time.

An external GitHub Actions scheduled workflow calls /run-check every 15
minutes on weekdays. Both endpoints require a shared-secret token (RUN_TOKEN
env var) so a random visitor to the public dashboard can't trigger trades.
"""
import os
import sys
import io
import secrets as secrets_module
import threading
import contextlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify
import config
import db

app = Flask(__name__)

_backtest_lock = threading.Lock()
_backtest_running = False


def _check_token():
    token = request.args.get("token", "")
    if not config.RUN_TOKEN:
        return False  # never allow if no token configured server-side
    return secrets_module.compare_digest(token, config.RUN_TOKEN)


@app.route("/")
def index():
    mode = request.args.get("mode", "live")
    trades = db.get_all_trades(mode=mode, limit=500)
    summary = db.get_summary(mode)
    resp = render_template("index.html", trades=trades, summary=summary, mode=mode,
                            backtest_running=_backtest_running)
    response = app.response_class(resp)
    # No caching -- this page shows live trade state; a cached response
    # (browser or any intermediate proxy/CDN) previously caused stale data
    # to be served regardless of the ?mode= query string.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/run-check")
def run_check():
    if not _check_token():
        return jsonify({"error": "unauthorized"}), 403

    import live_check
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            live_check.main()
        return jsonify({"status": "ok", "log": buf.getvalue()})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e), "log": buf.getvalue()}), 500


@app.route("/run-backtest")
def run_backtest_route():
    global _backtest_running
    if not _check_token():
        return jsonify({"error": "unauthorized"}), 403

    with _backtest_lock:
        if _backtest_running:
            return jsonify({"status": "already_running",
                             "message": "Backtest already in progress -- check the Backtest tab."})
        _backtest_running = True

    def _run():
        global _backtest_running
        import backtest
        try:
            backtest.run_backtest()
        except Exception as e:
            print(f"Backtest thread error: {e}")
        finally:
            _backtest_running = False

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started",
                     "message": "Backtest started in background. Watch the Backtest tab -- "
                                "trades will appear there as they're simulated. "
                                "Takes roughly 20-30 minutes."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
