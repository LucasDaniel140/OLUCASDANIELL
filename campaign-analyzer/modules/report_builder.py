"""
Report builder.

Generates a professional, standalone HTML report for client delivery.
Uses client-friendly language — no internal terms like "score", "Pausar", etc.

The returned HTML string is self-contained (CSS embedded) and ready for
print-to-PDF via the browser.
"""

import html as _html
from datetime import datetime

# ---------------------------------------------------------------------------
# Client-facing label maps
# ---------------------------------------------------------------------------

_PLATFORM_LABELS = {"meta": "Meta Ads", "google": "Google Ads"}

_STATUS_CLIENT_MAP = {
    "Escalar":  ("Destaque",   "badge-destaque"),
    "Manter":   ("Estável",    "badge-estavel"),
    "Otimizar": ("Em ajuste",  "badge-ajuste"),
    "Pausar":   ("Em revisão", "badge-revisao"),
}

_ALERT_TRANSLATIONS = {
    "ctr_critical": (
        'A campanha "{camp}" apresenta baixo engajamento com o público — '
        "recomendamos revisão dos criativos e da segmentação."
    ),
    "cpa_high": (
        'O custo por resultado da campanha "{camp}" está acima do esperado — '
        "ajustes de segmentação estão sendo avaliados."
    ),
    "no_conversion": (
        'A campanha "{camp}" registrou investimento sem resultados no período — será revisada.'
    ),
    "roas_negative": (
        'O retorno sobre investimento da campanha "{camp}" está abaixo do esperado — '
        "revisão de estratégia em andamento."
    ),
    "landing_page": (
        'A campanha "{camp}" apresenta boa atração de cliques, mas baixa taxa de conversão — '
        "recomendamos revisão da página de destino e da oferta."
    ),
}

# Simple text replacements to strip internal jargon from recommendations
_REC_REPLACEMENTS = [
    ("Pausar ",             "Suspender temporariamente "),
    (" o budget",           " o orçamento"),
    (" budget ",            " orçamento "),
    ("status 'Otimizar'",   "performance abaixo do esperado"),
    ("fase de aprendizado e ", ""),
    ("landing page",        "página de destino"),
    ("funil de conversão",  "fluxo de conversão"),
    ("UGC",                 "conteúdo de clientes"),
    ("CTR médio",           "taxa de cliques"),
    ("CTR bom",             "boa taxa de cliques"),
    ("CPA alto",            "custo por resultado elevado"),
    ("o ROAS médio está abaixo de 1.5x",
     "o retorno sobre investimento está abaixo do esperado"),
    ("ROAS médio",          "retorno sobre investimento"),
]

# ---------------------------------------------------------------------------
# CSS — embedded in the report <style> block
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  color: #1a1a2e;
  background: #ffffff;
  line-height: 1.55;
}
.container { max-width: 960px; margin: 0 auto; padding: 48px 40px; }

/* ── Header ─────────────────────────────────────────────────── */
.report-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding-bottom: 24px;
  margin-bottom: 36px;
  border-bottom: 2px solid #1a1a2e;
}
.logo-text {
  font-size: 22px;
  font-weight: 800;
  color: #1a1a2e;
  letter-spacing: -0.5px;
}
.logo-tagline {
  font-size: 11px;
  color: #888;
  margin-top: 3px;
  letter-spacing: .07em;
  text-transform: uppercase;
}
.report-meta { text-align: right; }
.client-name { font-size: 20px; font-weight: 700; color: #1a1a2e; }
.meta-line { font-size: 12px; color: #666; margin-top: 5px; }

/* ── Sections ───────────────────────────────────────────────── */
.section { margin-bottom: 44px; }
.section-title {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: #999;
  padding-bottom: 10px;
  margin-bottom: 18px;
  border-bottom: 1px solid #e8e8e8;
}

/* ── Executive summary ──────────────────────────────────────── */
.exec-box {
  background: #f4f6fb;
  border-left: 4px solid #1a1a2e;
  padding: 18px 22px;
  border-radius: 0 6px 6px 0;
  font-size: 14px;
  line-height: 1.8;
  color: #333;
}

/* ── KPI strip ──────────────────────────────────────────────── */
.kpi-strip {
  display: flex;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
  margin-top: 20px;
}
.kpi-item {
  flex: 1;
  padding: 14px 16px;
  border-right: 1px solid #e8e8e8;
  text-align: center;
}
.kpi-item:last-child { border-right: none; }
.kpi-label {
  font-size: 10px;
  color: #888;
  text-transform: uppercase;
  letter-spacing: .06em;
  margin-bottom: 5px;
}
.kpi-value { font-size: 17px; font-weight: 700; color: #1a1a2e; }

/* ── Campaign table ─────────────────────────────────────────── */
.camp-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.camp-table thead th {
  background: #1a1a2e;
  color: #fff;
  padding: 10px 12px;
  font-weight: 600;
  font-size: 12px;
  text-align: left;
  white-space: nowrap;
}
.camp-table thead th:not(:first-child) { text-align: right; }
.camp-table tbody tr:nth-child(even) { background: #f8f9fa; }
.camp-table tbody td {
  padding: 10px 12px;
  border-bottom: 1px solid #e9ecef;
  vertical-align: middle;
}
.camp-table tbody td:not(:first-child) { text-align: right; white-space: nowrap; }
.camp-name { font-weight: 600; max-width: 210px; word-break: break-word; }

/* ── Status badges ──────────────────────────────────────────── */
.badge {
  display: inline-block;
  padding: 3px 9px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.badge-destaque { background: #d4edda; color: #155724; }
.badge-estavel  { background: #d1ecf1; color: #0c5460; }
.badge-ajuste   { background: #fff3cd; color: #856404; }
.badge-revisao  { background: #f8d7da; color: #721c24; }

/* ── Attention items ────────────────────────────────────────── */
.attention-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: #fff8f8;
  border-left: 3px solid #dc3545;
  padding: 12px 16px;
  border-radius: 0 6px 6px 0;
  margin-bottom: 10px;
  font-size: 13px;
  line-height: 1.6;
  color: #444;
}
.attention-icon { font-size: 15px; flex-shrink: 0; padding-top: 1px; }

/* ── Next steps ─────────────────────────────────────────────── */
.steps-list { list-style: none; }
.steps-list li {
  display: flex;
  gap: 14px;
  padding: 11px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
  line-height: 1.6;
  color: #333;
}
.steps-list li:last-child { border-bottom: none; }
.step-arrow { color: #1a1a2e; font-weight: 800; flex-shrink: 0; padding-top: 2px; }

/* ── Footer ─────────────────────────────────────────────────── */
.report-footer {
  margin-top: 56px;
  padding-top: 16px;
  border-top: 1px solid #e0e0e0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 11px;
  color: #999;
}
.footer-brand { font-weight: 600; color: #666; }

/* ── Print button (hidden on print) ────────────────────────── */
.print-btn {
  position: fixed;
  bottom: 28px;
  right: 28px;
  background: #1a1a2e;
  color: #fff;
  padding: 12px 22px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  box-shadow: 0 4px 16px rgba(0,0,0,.25);
}
.print-btn:hover { background: #2d3a6e; }

/* ── Print media ────────────────────────────────────────────── */
@media print {
  .print-btn { display: none !important; }
  body { font-size: 12px; }
  .container { padding: 0; max-width: 100%; }
  .exec-box, .kpi-strip, .kpi-item,
  .camp-table thead th, .badge,
  .attention-item {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
}
"""

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_report(analysis: dict) -> str:
    """Return a complete standalone HTML report string."""
    summary         = analysis.get("summary", {})
    campaigns       = analysis.get("campaigns", [])
    alerts          = analysis.get("alerts", [])[:3]
    recommendations = analysis.get("recommendations", [])
    client          = analysis.get("client", "")
    platform        = analysis.get("platform", "")
    period          = analysis.get("period", "—")
    generated_at    = _format_dt(analysis.get("generated_at", ""))
    platform_label  = _PLATFORM_LABELS.get(platform, platform)

    parts = [
        "<!DOCTYPE html>",
        '<html lang="pt-BR">',
        "<head>",
        '  <meta charset="utf-8" />',
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />',
        f"  <title>Relatório — {_e(client)} — {_e(period)}</title>",
        f"  <style>{_CSS}</style>",
        "</head>",
        "<body>",
        '<div class="container">',
        _header(client, platform_label, period, generated_at),
        _section_executive(summary, campaigns, analysis),
        _section_campaigns(campaigns, summary),
        _section_alerts(alerts),
        _section_steps(recommendations),
        _footer(generated_at),
        "</div>",
        (
            '<button class="print-btn" onclick="window.print()">'
            "&#128438;&nbsp; Imprimir / Salvar como PDF"
            "</button>"
        ),
        "</body>",
        "</html>",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _header(client: str, platform_label: str, period: str, generated_at: str) -> str:
    return (
        '<header class="report-header">'
        "  <div>"
        '    <div class="logo-text">Ag&ecirc;ncia Candeeiro</div>'
        '    <div class="logo-tagline">Gest&atilde;o de Tr&aacute;fego Pago</div>'
        "  </div>"
        '  <div class="report-meta">'
        f'    <div class="client-name">{_e(client)}</div>'
        f'    <div class="meta-line">{_e(platform_label)} &middot; {_e(period)}</div>'
        f'    <div class="meta-line">Relat&oacute;rio gerado em {_e(generated_at)}</div>'
        "  </div>"
        "</header>"
    )


def _section_executive(summary: dict, campaigns: list, analysis: dict) -> str:
    paragraph = _executive_paragraph(summary, campaigns)
    kpi_html  = _kpi_strip(summary)
    return (
        '<section class="section">'
        '  <div class="section-title">Resumo Executivo</div>'
        f'  <div class="exec-box">{paragraph}</div>'
        f"  {kpi_html}"
        "</section>"
    )


def _executive_paragraph(summary: dict, campaigns: list) -> str:
    n       = len(campaigns)
    plural  = "s" if n != 1 else ""
    spend   = _brl(summary.get("total_spend", 0))
    avg_ctr = summary.get("avg_ctr", 0)
    avg_cpm = summary.get("avg_cpm", 0)

    text = (
        f"No per&iacute;odo analisado, foram investidos <strong>{spend}</strong> "
        f"distribu&iacute;dos em <strong>{n} campanha{plural} ativa{plural}</strong>."
    )

    best_name = summary.get("best_campaign")
    if best_name:
        best = next((c for c in campaigns if c["campaign_name"] == best_name), None)
        if best:
            if best.get("conversions", 0) > 0:
                n_conv    = best["conversions"]
                conv_word = "convers&otilde;es" if n_conv > 1 else "convers&atilde;o"
                text += (
                    f' A campanha <strong>&ldquo;{_e(best_name)}&rdquo;</strong>'
                    f" apresentou o melhor desempenho, gerando"
                    f" <strong>{n_conv} {conv_word}</strong>"
                    f" com custo por resultado de <strong>{_brl(best['cpa'])}</strong>."
                )
            else:
                text += (
                    f' A campanha <strong>&ldquo;{_e(best_name)}&rdquo;</strong>'
                    " apresentou o melhor engajamento do per&iacute;odo."
                )

    text += (
        f" No geral, as campanhas registraram CTR m&eacute;dio de"
        f" <strong>{avg_ctr:.2f}%</strong>"
        f" e CPM de <strong>{_brl(avg_cpm)}</strong>."
    )

    if summary.get("has_revenue") and summary.get("avg_roas", 0) > 0:
        roas = summary["avg_roas"]
        text += (
            f" O retorno sobre o investimento (ROAS) m&eacute;dio foi de"
            f" <strong>{roas:.2f}x</strong>."
        )

    return text


def _kpi_strip(summary: dict) -> str:
    items = [
        ("Total investido",  _brl(summary.get("total_spend", 0))),
        ("Impress&otilde;es", _num(summary.get("total_impressions", 0))),
        ("Cliques",          _num(summary.get("total_clicks", 0))),
        ("Convers&otilde;es", _num(summary.get("total_conversions", 0))),
        ("CTR m&eacute;dio", _pct(summary.get("avg_ctr", 0))),
    ]
    if summary.get("total_conversions", 0) > 0:
        items.append(("CPA m&eacute;dio", _brl(summary.get("avg_cpa", 0))))
    if summary.get("has_revenue") and summary.get("avg_roas", 0) > 0:
        items.append(("ROAS m&eacute;dio", f"{summary['avg_roas']:.2f}x"))

    cells = "".join(
        f'<div class="kpi-item">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f"</div>"
        for label, value in items
    )
    return f'<div class="kpi-strip">{cells}</div>'


def _section_campaigns(campaigns: list, summary: dict) -> str:
    has_revenue = summary.get("has_revenue", False)
    roas_th     = "<th>ROAS</th>" if has_revenue else ""

    rows = []
    for c in campaigns:
        label, badge_cls = _STATUS_CLIENT_MAP.get(
            c.get("status", ""), ("—", "badge-estavel")
        )
        cpa_val  = c.get("cpa", 0)
        roas_val = c.get("roas", 0)
        conv_val = c.get("conversions", 0)

        roas_td = (
            f"<td>{roas_val:.2f}x</td>" if (has_revenue and roas_val > 0) else
            ("<td>&mdash;</td>" if has_revenue else "")
        )

        rows.append(
            "<tr>"
            f'<td class="camp-name">{_e(c.get("campaign_name", "—"))}</td>'
            f"<td>{_brl(c.get('spend', 0))}</td>"
            f"<td>{_num(c.get('impressions', 0))}</td>"
            f"<td>{_num(c.get('clicks', 0))}</td>"
            f"<td>{_pct(c.get('ctr', 0))}</td>"
            f"<td>{_brl(c.get('cpc', 0))}</td>"
            f"<td>{'&mdash;' if conv_val == 0 else _num(conv_val)}</td>"
            f"<td>{'&mdash;' if cpa_val == 0 else _brl(cpa_val)}</td>"
            f"{roas_td}"
            f'<td><span class="badge {badge_cls}">{label}</span></td>'
            "</tr>"
        )

    rows_html = "\n".join(rows)
    return (
        '<section class="section">'
        '  <div class="section-title">Performance por Campanha</div>'
        '  <table class="camp-table">'
        "    <thead><tr>"
        "      <th>Campanha</th>"
        "      <th>Investimento</th>"
        "      <th>Impress&otilde;es</th>"
        "      <th>Cliques</th>"
        "      <th>CTR</th>"
        "      <th>CPC</th>"
        "      <th>Convers&otilde;es</th>"
        "      <th>CPA</th>"
        f"      {roas_th}"
        "      <th>Situa&ccedil;&atilde;o</th>"
        "    </tr></thead>"
        f"    <tbody>{rows_html}</tbody>"
        "  </table>"
        "</section>"
    )


def _section_alerts(alerts: list) -> str:
    if not alerts:
        return ""

    items = "".join(
        f'<div class="attention-item">'
        f'<span class="attention-icon">&#9888;</span>'
        f"<span>{_translate_alert(a)}</span>"
        f"</div>"
        for a in alerts
    )
    return (
        '<section class="section">'
        '  <div class="section-title">Pontos de Aten&ccedil;&atilde;o</div>'
        f"  {items}"
        "</section>"
    )


def _section_steps(recommendations: list) -> str:
    if not recommendations:
        return ""

    items = "".join(
        f"<li>"
        f'<span class="step-arrow">&rarr;</span>'
        f"<span>{_e(_client_rec(r))}</span>"
        f"</li>"
        for r in recommendations
    )
    return (
        '<section class="section">'
        '  <div class="section-title">Pr&oacute;ximos Passos</div>'
        f'  <ul class="steps-list">{items}</ul>'
        "</section>"
    )


def _footer(generated_at: str) -> str:
    return (
        '<footer class="report-footer">'
        f'  <span class="footer-brand">'
        f"Relat&oacute;rio gerado por Ag&ecirc;ncia Candeeiro &middot; {_e(generated_at)}"
        f"</span>"
        '  <span class="confidential">'
        "Este relat&oacute;rio &eacute; de uso exclusivo do cliente e cont&eacute;m"
        " informa&ccedil;&otilde;es confidenciais."
        "</span>"
        "</footer>"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _e(text) -> str:
    """HTML-escape a value."""
    return _html.escape(str(text) if text is not None else "")


def _brl(value) -> str:
    try:
        f = f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {f}"
    except (ValueError, TypeError):
        return "&mdash;"


def _pct(value) -> str:
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return "&mdash;"


def _num(value) -> str:
    try:
        return f"{int(float(value)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "&mdash;"


def _format_dt(iso_str: str) -> str:
    try:
        return datetime.fromisoformat(iso_str).strftime("%d/%m/%Y às %H:%M")
    except (ValueError, TypeError, AttributeError):
        return datetime.now().strftime("%d/%m/%Y às %H:%M")


def _translate_alert(alert: dict) -> str:
    template = _ALERT_TRANSLATIONS.get(alert.get("type", ""))
    if template:
        return template.format(camp=_e(alert.get("campaign", "")))
    return (
        f'A campanha &ldquo;{_e(alert.get("campaign", ""))}&rdquo;'
        " requer aten&ccedil;&atilde;o especial no per&iacute;odo analisado."
    )


def _client_rec(rec: dict) -> str:
    action = rec.get("action", "")
    for old, new in _REC_REPLACEMENTS:
        action = action.replace(old, new)
    return action
