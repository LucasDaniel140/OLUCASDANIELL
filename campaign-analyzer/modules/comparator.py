"""
Comparator module.

Takes two analysis dicts (from /reports/*.json) and produces a structured
comparison result with metric deltas, campaign-level diffs, a diagnostic
paragraph, and comparative recommendations.
"""

from __future__ import annotations

from typing import Optional

# ── Summary metrics: (key, label, higher_is_better, format_type) ────────────
_SUMMARY_METRICS: list[tuple] = [
    ("total_spend",       "Total Investido",  False, "brl"),
    ("total_impressions", "Impressões",        True,  "num"),
    ("total_clicks",      "Cliques",           True,  "num"),
    ("avg_ctr",           "CTR médio",         True,  "pct"),
    ("avg_cpc",           "CPC médio",         False, "brl"),
    ("avg_cpm",           "CPM médio",         False, "brl"),
    ("total_conversions", "Conversões",        True,  "num"),
    ("avg_cpa",           "CPA médio",         False, "brl"),
    ("avg_roas",          "ROAS médio",        True,  "x"),
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compare(analysis_a: dict, analysis_b: dict) -> dict:
    """
    Compare two analysis dicts.

    analysis_a → Período A (reference / older)
    analysis_b → Período B (compared / newer)

    Returns a dict ready to be passed to the compare.html template.
    """
    s_a = analysis_a.get("summary", {})
    s_b = analysis_b.get("summary", {})

    has_revenue = s_a.get("has_revenue", False) or s_b.get("has_revenue", False)
    has_conv    = (s_a.get("total_conversions", 0) or 0) > 0 or \
                  (s_b.get("total_conversions", 0) or 0) > 0

    # ── Summary rows ─────────────────────────────────────────────────────────
    summary_rows: list[dict] = []
    for key, label, higher_is_better, fmt in _SUMMARY_METRICS:
        if key == "avg_roas" and not has_revenue:
            continue
        if key == "avg_cpa" and not has_conv:
            continue

        val_a = float(s_a.get(key, 0) or 0)
        val_b = float(s_b.get(key, 0) or 0)

        summary_rows.append({
            "key":              key,
            "label":            label,
            "value_a":          val_a,
            "value_b":          val_b,
            "delta_pct":        _delta(val_a, val_b),
            "higher_is_better": higher_is_better,
            "fmt":              fmt,
        })

    # ── Campaign-level comparison ─────────────────────────────────────────────
    camps_a = {c["campaign_name"]: c for c in analysis_a.get("campaigns", [])}
    camps_b = {c["campaign_name"]: c for c in analysis_b.get("campaigns", [])}

    names_both   = set(camps_a) & set(camps_b)
    names_only_a = set(camps_a) - set(camps_b)
    names_only_b = set(camps_b) - set(camps_a)

    camps_both = sorted(
        [_camp_row(camps_a[n], camps_b[n]) for n in names_both],
        key=lambda r: r["spend_b"], reverse=True,
    )
    camps_only_a = sorted(
        [camps_a[n] for n in names_only_a],
        key=lambda c: c.get("spend", 0), reverse=True,
    )
    camps_only_b = sorted(
        [camps_b[n] for n in names_only_b],
        key=lambda c: c.get("spend", 0), reverse=True,
    )

    # ── Scalar deltas for diagnosis / recommendations ─────────────────────────
    cpa_delta  = _delta(float(s_a.get("avg_cpa",  0) or 0), float(s_b.get("avg_cpa",  0) or 0))
    ctr_delta  = _delta(float(s_a.get("avg_ctr",  0) or 0), float(s_b.get("avg_ctr",  0) or 0))
    roas_delta = _delta(float(s_a.get("avg_roas", 0) or 0), float(s_b.get("avg_roas", 0) or 0)) \
                 if has_revenue else None
    conv_a     = int(s_a.get("total_conversions", 0) or 0)
    conv_b     = int(s_b.get("total_conversions", 0) or 0)
    conv_delta = _delta(float(conv_a), float(conv_b))

    diagnosis       = _build_diagnosis(cpa_delta, ctr_delta, roas_delta, conv_a, conv_b, has_revenue)
    recommendations = _build_recommendations(cpa_delta, ctr_delta, conv_delta, camps_both, camps_only_b)

    return {
        "client_a":        analysis_a.get("client", "—"),
        "client_b":        analysis_b.get("client", "—"),
        "same_client":     analysis_a.get("client") == analysis_b.get("client"),
        "period_a":        analysis_a.get("period", "—"),
        "period_b":        analysis_b.get("period", "—"),
        "platform_a":      analysis_a.get("platform", "—"),
        "platform_b":      analysis_b.get("platform", "—"),
        "generated_at_a":  analysis_a.get("generated_at", ""),
        "generated_at_b":  analysis_b.get("generated_at", ""),
        "has_revenue":     has_revenue,
        "summary_rows":    summary_rows,
        "camps_both":      camps_both,
        "camps_only_a":    camps_only_a,
        "camps_only_b":    camps_only_b,
        "diagnosis":       diagnosis,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _delta(a: float, b: float) -> Optional[float]:
    """Percentage change of b relative to a. None when base is zero."""
    if a == 0:
        return None
    return round((b - a) / abs(a) * 100, 1)


def _camp_row(ca: dict, cb: dict) -> dict:
    cpa_a = float(ca.get("cpa", 0) or 0)
    cpa_b = float(cb.get("cpa", 0) or 0)
    ctr_a = float(ca.get("ctr", 0) or 0)
    ctr_b = float(cb.get("ctr", 0) or 0)
    return {
        "campaign_name": ca["campaign_name"],
        "spend_a":       float(ca.get("spend", 0) or 0),
        "spend_b":       float(cb.get("spend", 0) or 0),
        "cpa_a":         cpa_a,
        "cpa_b":         cpa_b,
        "delta_cpa":     _delta(cpa_a, cpa_b),
        "ctr_a":         ctr_a,
        "ctr_b":         ctr_b,
        "delta_ctr":     _delta(ctr_a, ctr_b),
        "conv_a":        int(ca.get("conversions", 0) or 0),
        "conv_b":        int(cb.get("conversions", 0) or 0),
        "status_a":      ca.get("status", "—"),
        "status_b":      cb.get("status", "—"),
    }


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------

def _build_diagnosis(
    cpa_delta:  Optional[float],
    ctr_delta:  Optional[float],
    roas_delta: Optional[float],
    conv_a: int,
    conv_b: int,
    has_revenue: bool,
) -> str:
    parts: list[str] = []

    # CPA movement
    if cpa_delta is not None:
        if cpa_delta < -10:
            parts.append(
                f"O custo por resultado melhorou {abs(cpa_delta):.1f}%"
                " em relação ao período anterior."
            )
        elif cpa_delta > 10:
            parts.append(
                f"O custo por resultado piorou {cpa_delta:.1f}%"
                " — recomenda-se revisão de segmentação ou criativos."
            )

    # CTR movement
    if ctr_delta is not None:
        if ctr_delta > 5:
            parts.append(
                "O engajamento com os anúncios aumentou,"
                " indicando melhora nos criativos ou na segmentação."
            )
        elif ctr_delta < -10:
            parts.append(
                "O engajamento com os anúncios caiu,"
                " sugerindo necessidade de renovação de criativos."
            )

    # CTR up but conversions dropped → funnel issue
    if ctr_delta is not None and ctr_delta > 0 and conv_a > 0 and conv_b < conv_a:
        parts.append(
            "O aumento de cliques não se converteu em resultados"
            " — possível problema no funil pós-clique ou na oferta."
        )

    # ROAS movement
    if has_revenue and roas_delta is not None:
        if roas_delta > 10:
            parts.append(
                f"O retorno sobre investimento cresceu {roas_delta:.1f}%,"
                " indicando campanhas mais eficientes."
            )
        elif roas_delta < -10:
            parts.append(
                "O retorno sobre investimento caiu em relação ao período anterior"
                " — revisar mix de campanhas e ofertas."
            )

    if not parts:
        parts.append(
            "Não houve variações significativas entre os dois períodos analisados."
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Comparative recommendations
# ---------------------------------------------------------------------------

def _build_recommendations(
    cpa_delta:   Optional[float],
    ctr_delta:   Optional[float],
    conv_delta:  Optional[float],
    camps_both:  list,
    camps_only_b: list,
) -> list[dict]:
    recs: list[dict] = []

    # Campaigns that improved CPA → scale
    improved = [c for c in camps_both if c["delta_cpa"] is not None and c["delta_cpa"] < -10]
    if improved:
        names = ", ".join(f'"{c["campaign_name"]}"' for c in improved[:2])
        suffix = f" e mais {len(improved) - 2}" if len(improved) > 2 else ""
        recs.append({
            "action": (
                f"Manter e considerar aumento de orçamento em {names}{suffix},"
                " que apresentaram redução de CPA no período."
            ),
            "impact": "Reforçar campanhas eficientes acelera a queda no CPA geral da conta.",
        })

    # Campaigns that worsened CPA → review
    worsened = [c for c in camps_both if c["delta_cpa"] is not None and c["delta_cpa"] > 20]
    if worsened:
        names = ", ".join(f'"{c["campaign_name"]}"' for c in worsened[:2])
        suffix = f" e mais {len(worsened) - 2}" if len(worsened) > 2 else ""
        recs.append({
            "action": (
                f"Revisar segmentação e criativos de {names}{suffix},"
                " que registraram aumento significativo de CPA."
            ),
            "impact": "Corrigir a causa do aumento de CPA evita desperdício continuado de orçamento.",
        })

    # CTR dropped → new creatives
    if ctr_delta is not None and ctr_delta < -10:
        recs.append({
            "action": (
                "Renovar criativos das campanhas com queda de engajamento"
                " — testar novos formatos, ângulos ou mensagens."
            ),
            "impact": "Criativos frescos reativam a atenção do público e melhoram a taxa de cliques.",
        })

    # CTR up but conversions down → landing page
    if ctr_delta is not None and ctr_delta > 0 and conv_delta is not None and conv_delta < 0:
        recs.append({
            "action": (
                "Revisar a página de destino e o fluxo de conversão"
                " — os cliques aumentaram mas os resultados caíram."
            ),
            "impact": "Melhorar a experiência pós-clique é o alavancamento de maior impacto no momento.",
        })

    # New campaigns in period B → monitor
    if camps_only_b:
        recs.append({
            "action": (
                "Monitorar de perto as novas campanhas do Período B"
                " para avaliar maturação e potencial de escala."
            ),
            "impact": "Novas campanhas precisam de acompanhamento próximo nas primeiras semanas para calibração.",
        })

    return recs[:3]
