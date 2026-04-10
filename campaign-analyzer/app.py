import os
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, url_for

from config import Config
from modules.analyzer import analyze
from modules.google_parser import GoogleParser
from modules.meta_parser import MetaParser
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
        formatted = f"{float(value):,.2f}"          # "1,234.56"
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted}"
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    # ── Validate form fields ──────────────────────────────────────────────────
    client_name = request.form.get("client_name", "").strip()
    platform = request.form.get("platform", "").strip()
    date_start = request.form.get("date_start", "").strip()
    date_end = request.form.get("date_end", "").strip()

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

    # ── Save file ─────────────────────────────────────────────────────────────
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

    return render_template(
        "analysis.html",
        result=result,
        platform=platform,
        platform_label=platform_label(platform),
        date_start=date_start,
        date_end=date_end,
        filename=filename,
    )


# ---------------------------------------------------------------------------
# Helpers
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
