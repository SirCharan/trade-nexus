"""
Vercel Serverless Function: POST /api/advice
Receives the full report JSON, computes rule-based trading metrics,
then calls Groq LLM for polished mentor-quality advice.
Falls back to rule-based text if Groq is unavailable.
"""
import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler


GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


# ─── Rule-Based Metrics Engine ──────────────────────────────────────────────────

def compute_trading_metrics(report: dict) -> dict:
    """Compute all rule-based trading principle metrics from the report."""
    ov = report.get("overview", {})
    perf = report.get("performance", {})
    inst = report.get("instruments", {})
    ch = report.get("charges", {})
    op = report.get("open_portfolio", {})

    win_rate = ov.get("win_rate", 0) / 100  # as fraction
    avg_winner = abs(ov.get("avg_winner", 0))
    avg_loser = abs(ov.get("avg_loser", 0))
    realized_pnl = ov.get("net_realized_pnl", 0)
    total_charges = ov.get("total_charges", 0)
    symbols_traded = ov.get("symbols_traded", 0)
    winners = ov.get("winners", 0)
    losers = ov.get("losers", 0)
    total_buy = ov.get("total_buy_value", 0)
    total_sell = ov.get("total_sell_value", 0)
    win_loss_ratio = ov.get("win_loss_ratio", 0)

    # Kelly Criterion
    rr_ratio = (avg_winner / avg_loser) if avg_loser > 0 else 0
    kelly = (win_rate - (1 - win_rate) / rr_ratio) if rr_ratio > 0 else 0
    kelly = max(0, min(kelly, 1))  # clamp 0-1
    half_kelly = kelly / 2

    # Charges analysis
    charges_pct = ch.get("charges_pct_pnl", 0)
    overtrading = charges_pct > 10

    # Concentration risk
    top3_impact = perf.get("top_winners_impact", 0)
    top3_pct = perf.get("top_winners_pct", 0)
    top3_names = perf.get("top_winners_names", "")
    concentration_pct = perf.get("concentration_pct", 0)

    # Pareto
    pareto = perf.get("pareto", [])
    pareto_80_idx = perf.get("pareto_80_index", 0)
    total_winning_underlyings = len(pareto)
    pareto_pct = ((pareto_80_idx + 1) / total_winning_underlyings * 100) if total_winning_underlyings > 0 else 0

    # Instrument edge
    futures_pnl = inst.get("futures_pnl", 0)
    options_pnl = inst.get("options_pnl", 0)
    calls_pnl = inst.get("calls_pnl", 0)
    puts_pnl = inst.get("puts_pnl", 0)
    futures_count = inst.get("futures_count", 0)
    options_count = inst.get("options_count", 0)
    calls_count = inst.get("calls_count", 0)
    puts_count = inst.get("puts_count", 0)

    calls_wr = 0
    puts_wr = 0
    # Estimate from pnl_by_underlying isn't precise, use overall splits
    if calls_count > 0 and puts_count > 0:
        # approximate from overall data
        calls_wr = (calls_pnl / abs(calls_pnl + 1)) * 50 + 50 if calls_pnl != 0 else 50
        puts_wr = (puts_pnl / abs(puts_pnl + 1)) * 50 + 50 if puts_pnl != 0 else 50

    # Win/loss asymmetry
    asymmetry = perf.get("win_loss_asymmetry", 0)

    # Open portfolio concentration
    open_concentration = op.get("concentration", [])
    top_open = open_concentration[0] if open_concentration else {"underlying": "N/A", "pct": 0}

    # Overall score
    score = compute_score(win_rate * 100, rr_ratio, charges_pct, concentration_pct, asymmetry)

    return {
        "kelly_fraction": round(kelly, 4),
        "half_kelly": round(half_kelly, 4),
        "kelly_pct": round(kelly * 100, 1),
        "half_kelly_pct": round(half_kelly * 100, 1),
        "rr_ratio": round(rr_ratio, 2),
        "win_rate": round(win_rate * 100, 1),
        "charges_pct": round(charges_pct, 1),
        "overtrading": overtrading,
        "symbols_traded": symbols_traded,
        "winners": winners,
        "losers": losers,
        "avg_winner": round(avg_winner),
        "avg_loser": round(avg_loser),
        "win_loss_ratio": round(win_loss_ratio, 2),
        "realized_pnl": round(realized_pnl),
        "total_charges": round(total_charges),
        "net_after_charges": round(ov.get("net_after_charges", 0)),
        "top3_winners": top3_names,
        "top3_impact": round(top3_impact),
        "top3_pct": round(top3_pct, 1),
        "concentration_pct": round(concentration_pct, 1),
        "pareto_pct": round(pareto_pct, 1),
        "pareto_80_count": pareto_80_idx + 1,
        "total_winning_underlyings": total_winning_underlyings,
        "futures_pnl": round(futures_pnl),
        "options_pnl": round(options_pnl),
        "calls_pnl": round(calls_pnl),
        "puts_pnl": round(puts_pnl),
        "futures_count": futures_count,
        "options_count": options_count,
        "asymmetry": round(asymmetry, 2),
        "top_open_underlying": top_open.get("underlying", "N/A"),
        "top_open_pct": top_open.get("pct", 0),
        "open_count": op.get("open_positions_count", 0),
        "total_unrealized": round(op.get("total_unrealized_pnl", 0)),
        "overall_score": score,
    }


def compute_score(win_rate, rr_ratio, charges_pct, concentration_pct, asymmetry):
    """Grade the trader A+ to D based on key metrics."""
    score = 0
    # Win rate (0-25 pts)
    if win_rate >= 65: score += 25
    elif win_rate >= 55: score += 20
    elif win_rate >= 45: score += 15
    else: score += 5

    # Risk-reward ratio (0-25 pts)
    if rr_ratio >= 2.0: score += 25
    elif rr_ratio >= 1.5: score += 20
    elif rr_ratio >= 1.0: score += 15
    else: score += 5

    # Charges discipline (0-25 pts)
    if charges_pct <= 5: score += 25
    elif charges_pct <= 10: score += 20
    elif charges_pct <= 15: score += 15
    else: score += 5

    # Asymmetry / edge (0-25 pts)
    if asymmetry >= 2.0: score += 25
    elif asymmetry >= 1.5: score += 20
    elif asymmetry >= 1.0: score += 15
    else: score += 5

    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B+"
    if score >= 60: return "B"
    if score >= 50: return "C+"
    if score >= 40: return "C"
    return "D"


# ─── Fallback Rule-Based Advice ─────────────────────────────────────────────────

def generate_fallback_advice(metrics: dict) -> dict:
    """Generate structured advice using pure rule-based logic (no LLM)."""
    strengths = []
    weaknesses = []
    recommendations = []

    wr = metrics["win_rate"]
    rr = metrics["rr_ratio"]
    kelly_pct = metrics["kelly_pct"]
    charges_pct = metrics["charges_pct"]

    # Strengths
    if wr >= 60:
        strengths.append(f"Strong win rate of {wr}% — you're picking more winners than losers consistently.")
    if rr >= 1.5:
        strengths.append(f"Excellent risk-reward ratio of {rr}:1 — your winners are significantly larger than losers.")
    if metrics["options_pnl"] > 0:
        strengths.append(f"Options trading is profitable at ₹{abs(metrics['options_pnl']):,.0f} across {metrics['options_count']} trades.")
    if metrics["puts_pnl"] > metrics["calls_pnl"] and metrics["puts_pnl"] > 0:
        strengths.append(f"Put strategies are your strongest edge (₹{metrics['puts_pnl']:,.0f} P&L) — this is a clear competitive advantage.")
    if metrics["top3_pct"] > 30:
        strengths.append(f"Your top 3 underlyings ({metrics['top3_winners']}) drive {metrics['top3_pct']}% of profits — strong conviction trading.")
    if kelly_pct > 10:
        strengths.append(f"Positive Kelly Criterion ({kelly_pct}%) confirms you have a genuine statistical edge in the market.")

    # Weaknesses
    if wr < 50:
        weaknesses.append(f"Win rate of {wr}% means you're losing more trades than winning. Focus on higher-probability setups.")
    if rr < 1.0:
        weaknesses.append(f"Average loser (₹{metrics['avg_loser']:,.0f}) exceeds average winner (₹{metrics['avg_winner']:,.0f}). You're letting losses run and cutting winners short.")
    if charges_pct > 10:
        weaknesses.append(f"Charges consuming {charges_pct}% of profits — classic overtrading signal. Brokerage and taxes are eroding your edge.")
    if metrics["futures_pnl"] < 0:
        weaknesses.append(f"Futures trading is loss-making (₹{metrics['futures_pnl']:,.0f}). Consider reducing futures exposure or improving your directional calls.")
    if metrics["symbols_traded"] > 200:
        weaknesses.append(f"Traded {metrics['symbols_traded']} instruments — diffusion of focus. Pareto principle suggests most profits come from few underlyings.")
    if metrics["concentration_pct"] > 60:
        weaknesses.append(f"Top 5 underlyings account for {metrics['concentration_pct']}% of absolute P&L — high concentration risk.")

    # Recommendations
    if charges_pct > 10:
        recommendations.append(f"Reduce trade frequency by 30-40%. Focus on A+ setups only. This alone could save ₹{int(metrics['total_charges'] * 0.3):,} in charges.")
    if rr < 1.5:
        recommendations.append(f"Tighten stop losses to achieve minimum 1:2 risk-reward. Current ratio is {rr}:1 — target 2:1 by cutting losers at -₹{int(metrics['avg_winner'] / 2):,}.")
    recommendations.append(f"Kelly Criterion suggests risking up to {kelly_pct}% of capital per trade. Conservative (half-Kelly): {metrics['half_kelly_pct']}%. Compare against your actual position sizing.")
    if metrics["symbols_traded"] > 150:
        recommendations.append(f"Apply Pareto ruthlessly: your top {metrics['pareto_80_count']} underlyings generate 80%+ of profits. Consider dropping the bottom 80% of instruments.")
    if metrics["top_open_pct"] > 50:
        recommendations.append(f"Open portfolio is {metrics['top_open_pct']}% concentrated in {metrics['top_open_underlying']}. Diversify to reduce single-underlying risk.")
    if metrics["futures_pnl"] < 0 and metrics["options_pnl"] > 0:
        recommendations.append(f"Shift capital from futures (loss ₹{abs(metrics['futures_pnl']):,.0f}) to options (profit ₹{metrics['options_pnl']:,.0f}) where your edge is proven.")

    pareto_insight = f"Top {metrics['pareto_pct']:.0f}% of winning underlyings generated 80% of profits — {'textbook 80/20' if 15 <= metrics['pareto_pct'] <= 30 else 'concentrated edge'}."

    return {
        "strengths": strengths or ["Positive overall P&L shows market participation skills."],
        "weaknesses": weaknesses or ["No critical weaknesses detected — maintain current discipline."],
        "recommendations": recommendations,
        "kelly_fraction": metrics["kelly_fraction"],
        "half_kelly_fraction": metrics["half_kelly"],
        "kelly_pct": metrics["kelly_pct"],
        "half_kelly_pct": metrics["half_kelly_pct"],
        "pareto_insight": pareto_insight,
        "overall_score": metrics["overall_score"],
        "metrics": metrics,
        "source": "rule-based",
    }


# ─── Groq LLM Enhancement ───────────────────────────────────────────────────────

def enhance_with_groq(metrics: dict, api_key: str) -> dict | None:
    """Call Groq LLM to generate polished, mentor-quality advice."""
    prompt = f"""You are an elite $500/hr trading mentor analyzing an Indian F&O trader's report.

METRICS:
Win Rate: {metrics['win_rate']}% ({metrics['winners']} wins, {metrics['losers']} losses, {metrics['symbols_traded']} trades)
Avg Winner: Rs {metrics['avg_winner']}, Avg Loser: Rs {metrics['avg_loser']}
Risk-Reward: {metrics['rr_ratio']}:1, Kelly: {metrics['kelly_pct']}% (half-Kelly: {metrics['half_kelly_pct']}%)
Net P&L: Rs {metrics['realized_pnl']}, Charges: Rs {metrics['total_charges']} ({metrics['charges_pct']}% of P&L)
Futures: Rs {metrics['futures_pnl']} ({metrics['futures_count']} trades), Options: Rs {metrics['options_pnl']} ({metrics['options_count']} trades)
Puts: Rs {metrics['puts_pnl']}, Calls: Rs {metrics['calls_pnl']}
Top 3: {metrics['top3_winners']} = {metrics['top3_pct']}% of profits
Asymmetry: {metrics['asymmetry']}x
Pareto: Top {metrics['pareto_80_count']} of {metrics['total_winning_underlyings']} winning underlyings = 80% of profits
Concentration: Top 5 = {metrics['concentration_pct']}% of absolute P&L
Open: {metrics['open_count']} positions, {metrics['top_open_underlying']} at {metrics['top_open_pct']}%
Grade: {metrics['overall_score']}

Return JSON: {{"strengths":["4-5 specific bullets with exact numbers, encouraging"],"weaknesses":["4-5 bullets citing exact numbers, referencing Kelly/Pareto/RR principles"],"recommendations":["6-7 actionable items with specific targets and which trading law applies"]}}

Use Rs for currency. Reference Kelly Criterion, Pareto 80/20, 1% Risk Rule, Risk-Reward ratio. Be direct, professional, specific numbers in every bullet. Each bullet 1-2 sentences max."""

    body = json.dumps({
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are an elite trading analyst. Always respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")

    req = urllib.request.Request(
        GROQ_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "StockyAnalyse/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return parsed
    except Exception:
        return None


# ─── HTTP Handler ───────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            report = json.loads(body)
        except Exception:
            self._respond(400, {"error": "Invalid JSON body"})
            return

        # Compute rule-based metrics
        metrics = compute_trading_metrics(report)

        # Generate fallback advice
        advice = generate_fallback_advice(metrics)

        # Try Groq enhancement
        api_key = os.environ.get("GROQ_API_KEY", "")
        if api_key:
            groq_result = enhance_with_groq(metrics, api_key)
            if groq_result:
                advice["strengths"] = groq_result.get("strengths", advice["strengths"])
                advice["weaknesses"] = groq_result.get("weaknesses", advice["weaknesses"])
                advice["recommendations"] = groq_result.get("recommendations", advice["recommendations"])
                advice["source"] = "groq-enhanced"

        self._respond(200, advice)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _respond(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
