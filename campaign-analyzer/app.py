import json
import os
import re
from datetime import datetime

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for

from config import Config
from modules.analyzer import analyze
from modules.google_parser import GoogleParser
from modules.meta_parser import MetaParser
from modules.report_builder import build_report
from modules.utils import allowed_file, generate_unique_filename, platform_label

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["REPORT_FOLDER"], exist_ok=True)


# ---------------------------------------------------------------------------
# Jinja2 filters
# ---------------------------------------------------------------------------

@app.template_filter("brl")
def brl_filter(value) -> str:
    """Format a number as Brazilian currency: R$ 1.234,56"""
    try:
        f = f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {f}"
    except (ValueError, TypeError):
        return "—"


@app.template_filter("pct")
def pct_filter(value) -> str:
    """Format a number as percentage: 1.23%"""
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return "—"


@app.template_filter("num")
def num_filter(value) -> str:
    """Format an integer with thousands separator: 1.234.567"""
    try:
        return f"{int(float(value)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "—"


@app.template_filter("fmtdt")
def fmtdt_filter(iso_str) -> str:
    """Format ISO datetime string for display."""
    try:
        return datetime.fromisoformat(str(iso_str)).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError, AttributeError):
        return str(iso_str)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    reports = _list_reports()
    return render_template("index.html", reports=reports)


@app.route("/upload", methods=["POST"])
def upload():
    # ── Validate form fields ──────────────────────────────────────────────────
    client_name = request.form.get("client_name", "").strip()
    platform    = request.form.get("platform", "").strip()
    date_start  = request.form.get("date_start", "").strip()
    date_end    = request.form.get("date_end", "").strip()

    if not client_name:
        flash("Nome do cliente é obrigatório.", "danger")
        return redirect(url_for("index"))

    if platform not in ("meta", "google"):
        flash("Selecione uma plataforma válida.", "danger")
        return redirect(url_for("index"))

    if "csv_file" not in request.files or request.files["csv_file"].filename == "":
        flash("Nenhum arquivo selecionado.", "danger")
        return redirect(url_for("index"))

    file = request.files["csv_file"]

    if not allowed_file(file.filename, app.config["ALLOWED_EXTENSIONS"]):
        flash("Apenas arquivos .csv são aceitos.", "danger")
        return redirect(url_for("index"))

    # ── Save CSV ──────────────────────────────────────────────────────────────
    filename = generate_unique_filename(client_name, file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # ── Parse ─────────────────────────────────────────────────────────────────
    try:
        parser = MetaParser(filepath) if platform == "meta" else GoogleParser(filepath)
        df = parser.parse()
    except Exception as exc:
        flash(f"Erro ao processar o arquivo: {exc}", "danger")
        return redirect(url_for("index"))

    # ── Analyze ───────────────────────────────────────────────────────────────
    period = _format_period(date_start, date_end)
    result = analyze(df, platform, client_name, period)

    # ── Persist analysis ──────────────────────────────────────────────────────
    analysis_id = _make_analysis_id(client_name)
    result["generated_at"] = datetime.now().isoformat()
    result["analysis_id"]  = analysis_id
    _save_analysis(result, analysis_id)

    return render_template(
        "analysis.html",
        result=result,
        analysis_id=analysis_id,
        platform=platform,
        platform_label=platform_label(platform),
        date_start=date_start,
        date_end=date_end,
        filename=filename,
    )


@app.route("/report/<analysis_id>")
def report(analysis_id):
    # Sanitize to prevent path traversal
    if not re.match(r"^[A-Za-z0-9_-]+$", analysis_id):
        abort(404)

    data = _load_analysis(analysis_id)
    if data is None:
        flash("Relatório não encontrado.", "danger")
        return redirect(url_for("index"))

    html = build_report(data)
    return Response(html, content_type="text/html; charset=utf-8")


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _make_analysis_id(client_name: str) -> str:
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name  = re.sub(r"[^a-zA-Z0-9]", "_", client_name).lower().strip("_")
    return f"{timestamp}_{safe_name}"


def _save_analysis(analysis: dict, analysis_id: str) -> None:
    path = os.path.join(app.config["REPORT_FOLDER"], f"{analysis_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(analysis, fh, ensure_ascii=False, indent=2, default=str)


def _load_analysis(analysis_id: str) -> dict | None:
    path = os.path.join(app.config["REPORT_FOLDER"], f"{analysis_id}.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _list_reports() -> list[dict]:
    """Return metadata for all saved analyses, newest first."""
    folder = app.config["REPORT_FOLDER"]
    entries = []
    try:
        filenames = sorted(
            (f for f in os.listdir(folder) if f.endswith(".json")),
            reverse=True,
        )
    except OSError:
        return []

    for fname in filenames:
        analysis_id = fname[:-5]
        path = os.path.join(folder, fname)
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            n_critical = sum(
                1 for a in data.get("alerts", []) if a.get("level") == "critical"
            )
            entries.append({
                "analysis_id":  analysis_id,
                "client":       data.get("client", "—"),
                "platform":     data.get("platform", "—"),
                "period":       data.get("period", "—"),
                "generated_at": data.get("generated_at", ""),
                "n_campaigns":  len(data.get("campaigns", [])),
                "n_alerts":     len(data.get("alerts", [])),
                "n_critical":   n_critical,
            })
        except Exception:
            continue

    return entries


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def _format_period(date_start: str, date_end: str) -> str:
    def fmt(d: str) -> str:
        try:
            return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            return d

    parts = [fmt(d) for d in (date_start, date_end) if d]
    return " → ".join(parts) if parts else "Período não informado"


if __name__ == "__main__":
    app.run(debug=True)
