import os

from flask import Flask, flash, redirect, render_template, request, url_for

from config import Config
from modules.google_parser import GoogleParser
from modules.meta_parser import MetaParser
from modules.utils import allowed_file, generate_unique_filename, platform_label

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["REPORT_FOLDER"], exist_ok=True)


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

    preview_records = df.head(5).to_dict("records")
    columns = list(df.columns)

    return render_template(
        "analysis.html",
        client_name=client_name,
        platform=platform,
        platform_label=platform_label(platform),
        date_start=date_start,
        date_end=date_end,
        filename=filename,
        total_rows=len(df),
        preview=preview_records,
        columns=columns,
    )


if __name__ == "__main__":
    app.run(debug=True)
