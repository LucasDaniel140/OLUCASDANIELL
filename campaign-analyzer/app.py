import json
import os
import re
from collections import defaultdict
from datetime import datetime

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for

from config import Config
from modules.analyzer import analyze
from modules.comparator import compare as compare_analyses
from modules.goals import get_goals, list_all_goals, save_goals
from modules.google_parser import GoogleParser
from modules.meta_parser import MetaParser
from modules.report_builder import build_report
from modules.utils import allowed_file, generate_unique_filename, normalize_slug, platform_label

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["REPORT_FOLDER"], exist_ok=True)
os.makedirs(app.config["DATA_FOLDER"], exist_ok=True)


# ---------------------------------------------------------------------------
# Jinja2 filters
# ---------------------------------------------------------------------------

@app.template_filter("brl")
def brl_filter(value) -> str:
    try:
        f = f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {f}"
    except (ValueError, TypeError):
        return "—"


@app.template_filter("pct")
def pct_filter(value) -> str:
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return "—"


@app.template_filter("num")
def num_filter(value) -> str:
    try:
        return f"{int(float(value)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "—"


@app.template_filter("fmtdt")
def fmtdt_filter(iso_str) -> str:
    try:
        return datetime.fromisoformat(str(iso_str)).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError, AttributeError):
        return str(iso_str)


@app.template_filter("fmtdate")
def fmtdate_filter(iso_str) -> str:
    try:
        return datetime.fromisoformat(str(iso_str)).strftime("%d/%m/%Y")
    except (ValueError, TypeError, AttributeError):
        return str(iso_str)


@app.template_filter("normalize_slug")
def normalize_slug_filter(name: str) -> str:
    return normalize_slug(str(name))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    reports = _list_reports()
    return render_template("index.html", reports=reports)


@app.route("/history")
def history():
    reports = _list_reports()
    groups  = _group_by_client(reports)
    return render_template("history.html", groups=groups, total=len(reports))


@app.route("/upload", methods=["POST"])
def upload():
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

    filename = generate_unique_filename(client_name, file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    try:
        parser = MetaParser(filepath) if platform == "meta" else GoogleParser(filepath)
        df = parser.parse()
    except Exception as exc:
        flash(f"Erro ao processar o arquivo: {exc}", "danger")
        return redirect(url_for("index"))

    period      = _format_period(date_start, date_end)
    client_slug = normalize_slug(client_name)
    goals       = get_goals(client_slug)
    result      = analyze(df, platform, client_name, period, goals=goals)

    analysis_id            = _make_analysis_id(client_name)
    result["generated_at"] = datetime.now().isoformat()
    result["analysis_id"]  = analysis_id
    _save_analysis(result, analysis_id)

    return render_template(
        "analysis.html",
        result=result,
        analysis_id=analysis_id,
        client_slug=client_slug,
        platform=platform,
        platform_label=platform_label(platform),
        date_start=date_start,
        date_end=date_end,
        filename=filename,
    )


@app.route("/report/<analysis_id>")
def report(analysis_id):
    if not re.match(r"^[A-Za-z0-9_-]+$", analysis_id):
        abort(404)
    data = _load_analysis(analysis_id)
    if data is None:
        flash("Relatório não encontrado.", "danger")
        return redirect(url_for("index"))
    return Response(build_report(data), content_type="text/html; charset=utf-8")


@app.route("/report/<analysis_id>/pdf")
def report_pdf(analysis_id):
    if not re.match(r"^[A-Za-z0-9_-]+$", analysis_id):
        abort(404)
    data = _load_analysis(analysis_id)
    if data is None:
        flash("Relatório não encontrado.", "danger")
        return redirect(url_for("index"))
    html_str = build_report(data)
    try:
        from weasyprint import HTML as WeasyprintHTML
        pdf_bytes = WeasyprintHTML(string=html_str).write_pdf()
        client    = re.sub(r"[^a-zA-Z0-9_-]", "_", data.get("client", "relatorio"))
        return Response(
            pdf_bytes,
            content_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="relatorio_{client}_{analysis_id}.pdf"'
                )
            },
        )
    except Exception:
        flash(
            "PDF temporariamente indisponível. Use 'Ver Relatório' e pressione"
            " Ctrl+P / Cmd+P no navegador para salvar como PDF.",
            "warning",
        )
        return redirect(url_for("report", analysis_id=analysis_id))


@app.route("/compare")
def compare():
    id_a = request.args.get("a", "").strip()
    id_b = request.args.get("b", "").strip()

    if not id_a or not id_b:
        flash("Selecione exatamente 2 análises para comparar.", "warning")
        return redirect(url_for("history"))

    if not re.match(r"^[A-Za-z0-9_-]+$", id_a) or not re.match(r"^[A-Za-z0-9_-]+$", id_b):
        abort(404)

    if id_a == id_b:
        flash("Selecione duas análises diferentes.", "warning")
        return redirect(url_for("history"))

    data_a = _load_analysis(id_a)
    data_b = _load_analysis(id_b)

    if data_a is None or data_b is None:
        flash("Uma ou mais análises não foram encontradas.", "danger")
        return redirect(url_for("history"))

    result = compare_analyses(data_a, data_b)

    return render_template(
        "compare.html",
        result=result,
        id_a=id_a,
        id_b=id_b,
    )


@app.route("/goals")
def goals():
    all_goals = list_all_goals()
    goal_slugs = {g["slug"] for g in all_goals}

    reports = _list_reports()
    groups  = _group_by_client(reports)
    clients_without_goals = [
        {"client": grp["client"], "slug": grp["slug"]}
        for grp in groups
        if grp["slug"] not in goal_slugs
    ]

    return render_template(
        "goals.html",
        clients_with_goals=all_goals,
        clients_without_goals=clients_without_goals,
    )


@app.route("/goals/<client_slug>", methods=["GET", "POST"])
def goals_form(client_slug):
    if not re.match(r"^[a-z0-9-]+$", client_slug):
        abort(404)

    if request.method == "POST":
        client_name = request.form.get("client_name", "").strip()
        if not client_name:
            flash("Nome do cliente é obrigatório.", "danger")
            return redirect(request.url)

        goals_data = {
            "target_cpa":      _form_float("target_cpa"),
            "min_roas":        _form_float("min_roas"),
            "min_ctr":         _form_float("min_ctr"),
            "max_cpc":         _form_float("max_cpc"),
            "monthly_budget":  _form_float("monthly_budget"),
        }
        save_goals(client_slug, client_name, goals_data)
        flash(f"Metas de {client_name} salvas com sucesso.", "success")
        return redirect(url_for("goals"))

    existing    = get_goals(client_slug)
    client_name = existing.get("client_name", "") if existing else ""

    if not client_name:
        reports = _list_reports()
        for r in reports:
            if normalize_slug(r["client"]) == client_slug:
                client_name = r["client"]
                break

    return render_template(
        "goals_form.html",
        client_slug=client_slug,
        client_name=client_name,
        goals=existing or {},
    )


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _make_analysis_id(client_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^a-zA-Z0-9]", "_", client_name).lower().strip("_")
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
            summary    = data.get("summary", {})
            n_critical = sum(1 for a in data.get("alerts", []) if a.get("level") == "critical")
            entries.append({
                "analysis_id":       analysis_id,
                "client":            data.get("client", "—"),
                "platform":          data.get("platform", "—"),
                "period":            data.get("period", "—"),
                "generated_at":      data.get("generated_at", ""),
                "n_campaigns":       len(data.get("campaigns", [])),
                "n_alerts":          len(data.get("alerts", [])),
                "n_critical":        n_critical,
                "total_spend":       summary.get("total_spend", 0),
                "total_conversions": summary.get("total_conversions", 0),
                "avg_cpa":           summary.get("avg_cpa", 0),
                "avg_ctr":           summary.get("avg_ctr", 0),
            })
        except Exception:
            continue

    return entries


def _group_by_client(reports: list) -> list[dict]:
    """Group report metadata by client, each group sorted newest-first."""
    bucket: dict[str, list] = defaultdict(list)
    for r in reports:
        bucket[r["client"]].append(r)

    groups = []
    for client, analyses in bucket.items():
        analyses.sort(key=lambda r: r.get("generated_at", ""), reverse=True)
        groups.append({
            "client":   client,
            "slug":     normalize_slug(client),
            "analyses": analyses,
        })

    groups.sort(key=lambda g: g["analyses"][0].get("generated_at", ""), reverse=True)
    return groups


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


def _form_float(field: str) -> float | None:
    """Extract an optional float from the current request form."""
    val = request.form.get(field, "").strip()
    if not val:
        return None
    try:
        return float(val.replace(",", "."))
    except ValueError:
        return None


if __name__ == "__main__":
    app.run(debug=True)
