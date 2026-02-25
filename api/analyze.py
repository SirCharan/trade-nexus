"""
Vercel Serverless Function: POST /api/analyze
Accepts a Zerodha tradebook CSV, runs FIFO trade matching + analytics, returns JSON.
Zero external dependencies — stdlib only.
"""
import json
import re
import csv
import io
import math
from http.server import BaseHTTPRequestHandler
from collections import defaultdict
from datetime import datetime


# ─── Constants ────────────────────────────────────────────────────────────────

INDEX_UNDERLYINGS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX"}
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri"]


# ─── Symbol Parser ────────────────────────────────────────────────────────────

def parse_symbol(symbol, expiry_date_str):
    """Parse Zerodha F&O symbol into structured components."""
    underlying_match = re.match(r"^([A-Z&]+?)(\d{2})", symbol)
    if not underlying_match:
        return {
            "underlying": symbol, "instrument_type": "UNKNOWN",
            "strike": "", "is_monthly": False, "is_index": False, "is_weekly": False,
        }

    underlying = underlying_match.group(1)
    rest = symbol[len(underlying):]

    instrument_type = "UNKNOWN"
    strike = ""
    is_monthly = False

    # Future: {YY}{MMM}FUT
    if re.match(r"^\d{2}(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)FUT$", rest):
        return {
            "underlying": underlying, "instrument_type": "FUT",
            "strike": "", "is_monthly": True,
            "is_index": underlying in INDEX_UNDERLYINGS, "is_weekly": False,
        }

    # Monthly option: {YY}{MMM}{STRIKE}{CE|PE}
    monthly_match = re.match(
        r"^(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d+(?:\.\d+)?)(CE|PE)$", rest
    )
    if monthly_match:
        return {
            "underlying": underlying, "instrument_type": monthly_match.group(4),
            "strike": monthly_match.group(3), "is_monthly": True,
            "is_index": underlying in INDEX_UNDERLYINGS, "is_weekly": False,
        }

    # Weekly option: {YY}{M}{DD}{STRIKE}{CE|PE}
    weekly_match = re.match(r"^(\d{2})([1-9OND])(\d{2})(\d+(?:\.\d+)?)(CE|PE)$", rest)
    if weekly_match:
        return {
            "underlying": underlying, "instrument_type": weekly_match.group(5),
            "strike": weekly_match.group(4), "is_monthly": False,
            "is_index": underlying in INDEX_UNDERLYINGS, "is_weekly": True,
        }

    # Fallback
    if symbol.endswith("CE"):
        instrument_type = "CE"
    elif symbol.endswith("PE"):
        instrument_type = "PE"
    elif "FUT" in symbol:
        instrument_type = "FUT"

    return {
        "underlying": underlying, "instrument_type": instrument_type,
        "strike": strike, "is_monthly": False,
        "is_index": underlying in INDEX_UNDERLYINGS, "is_weekly": True,
    }


# ─── CSV Parsing ──────────────────────────────────────────────────────────────

def parse_csv(csv_text):
    """Parse Zerodha tradebook CSV into list of execution dicts."""
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    for row in reader:
        # Normalize keys
        norm = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in row.items() if k}

        symbol = norm.get("symbol", norm.get("tradingsymbol", "")).strip()
        if not symbol:
            continue

        trade_type = norm.get("trade_type", "").strip().lower()
        if trade_type not in ("buy", "sell"):
            continue

        try:
            quantity = abs(float(norm.get("quantity", "0")))
            price = float(norm.get("price", "0"))
        except (ValueError, TypeError):
            continue

        if quantity <= 0 or price <= 0:
            continue

        # Use order_execution_time for precise ordering, fall back to trade_date
        exec_time = norm.get("order_execution_time", norm.get("trade_date", "")).strip()
        expiry_date = norm.get("expiry_date", "").strip()

        if not exec_time:
            continue

        rows.append({
            "symbol": symbol,
            "trade_type": trade_type,
            "quantity": quantity,
            "price": price,
            "exec_time": exec_time,
            "expiry_date": expiry_date,
        })
    return rows


# ─── FIFO Trade Matcher ──────────────────────────────────────────────────────

def match_trades(executions):
    """
    FIFO trade matching: convert raw executions into completed trades + open positions.
    Processes chronologically per symbol, handles partial fills and position flips.
    """
    by_symbol = defaultdict(list)
    for ex in executions:
        by_symbol[ex["symbol"]].append(ex)

    completed = []
    open_positions = []

    for symbol, execs in by_symbol.items():
        execs.sort(key=lambda x: x["exec_time"])

        parsed = parse_symbol(symbol, execs[0]["expiry_date"])
        inst_type = parsed["instrument_type"]

        position_queue = []
        position_side = None  # "buy" or "sell"

        for ex in execs:
            tt = ex["trade_type"]
            qty = ex["quantity"]
            price = ex["price"]

            if position_side is None:
                position_side = tt
                position_queue.append({"quantity": qty, "price": price, "exec_time": ex["exec_time"], "expiry_date": ex["expiry_date"]})
            elif tt == position_side:
                position_queue.append({"quantity": qty, "price": price, "exec_time": ex["exec_time"], "expiry_date": ex["expiry_date"]})
            else:
                # Opposite side — closing
                remaining_qty = qty
                while remaining_qty > 0.001 and position_queue:
                    entry = position_queue[0]
                    match_qty = min(remaining_qty, entry["quantity"])

                    entry_price = entry["price"]
                    exit_price = price

                    if position_side == "buy":
                        pnl = (exit_price - entry_price) * match_qty
                    else:
                        pnl = (entry_price - exit_price) * match_qty

                    capital = entry_price * match_qty
                    pnl_pct = (pnl / capital * 100) if capital > 0 else 0.0

                    entry_dt = _parse_date(entry["exec_time"][:10])
                    exit_dt = _parse_date(ex["exec_time"][:10])
                    expiry_dt = _parse_date(entry["expiry_date"])

                    hold_days = max((exit_dt - entry_dt).days, 0) if entry_dt and exit_dt else 0
                    dte = max((expiry_dt - entry_dt).days, 0) if expiry_dt and entry_dt else 0

                    # Direction: for PE, buy = short (bearish), sell = long (bullish)
                    if inst_type == "PE":
                        direction = "short" if position_side == "buy" else "long"
                    else:
                        direction = "long" if position_side == "buy" else "short"

                    completed.append({
                        "symbol": symbol,
                        "underlying": parsed["underlying"],
                        "instrument_type": inst_type,
                        "strike": parsed["strike"],
                        "direction": direction,
                        "entry_type": position_side,
                        "entry_date": entry["exec_time"][:10],
                        "exit_date": ex["exec_time"][:10],
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "quantity": int(match_qty),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "capital": round(capital, 2),
                        "hold_days": hold_days,
                        "dte": dte,
                        "is_weekly": parsed["is_weekly"],
                        "is_index": parsed["is_index"],
                        "is_monthly": parsed["is_monthly"],
                        "expiry_date": entry["expiry_date"],
                    })

                    entry["quantity"] -= match_qty
                    remaining_qty -= match_qty
                    if entry["quantity"] <= 0.001:
                        position_queue.pop(0)

                # Position flip: remaining qty starts new position in opposite direction
                if remaining_qty > 0.001:
                    position_side = tt
                    position_queue = [{"quantity": remaining_qty, "price": price, "exec_time": ex["exec_time"], "expiry_date": ex["expiry_date"]}]
                elif not position_queue:
                    position_side = None

        # Remaining in queue = open positions
        for entry in position_queue:
            if entry["quantity"] > 0.001:
                open_positions.append({
                    "symbol": symbol,
                    "underlying": parsed["underlying"],
                    "instrument_type": inst_type,
                    "strike": parsed["strike"],
                    "side": position_side or "buy",
                    "price": round(entry["price"], 2),
                    "quantity": int(entry["quantity"]),
                    "entry_date": entry["exec_time"][:10],
                    "expiry_date": entry.get("expiry_date", ""),
                    "is_index": parsed["is_index"],
                })

    completed.sort(key=lambda t: t["exit_date"])
    return completed, open_positions


def _parse_dt(s):
    """Parse datetime string like '2025-04-01T11:40:19' or '2025-04-01'."""
    try:
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, IndexError):
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except (ValueError, IndexError):
            return datetime(2025, 1, 1)


def _parse_date(s):
    """Parse date string like '2025-04-30'."""
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d")
    except (ValueError, IndexError):
        return None


# ─── Metrics Engine ───────────────────────────────────────────────────────────

def compute_all(trades, open_positions, filename):
    """Compute all 6 tab sections from matched trades."""
    if not trades:
        return _empty_response(filename, open_positions)

    # ── Common aggregates ──
    total_trades = len(trades)
    pnls = [t["pnl"] for t in trades]
    total_pnl = sum(pnls)
    winners = [t for t in trades if t["pnl"] > 0]
    losers = [t for t in trades if t["pnl"] <= 0]
    win_count = len(winners)
    loss_count = len(losers)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    sum_wins = sum(t["pnl"] for t in winners)
    sum_losses = abs(sum(t["pnl"] for t in losers))
    profit_factor = (sum_wins / sum_losses) if sum_losses > 0 else (999.99 if sum_wins > 0 else 0)
    avg_win = (sum_wins / win_count) if win_count > 0 else 0
    avg_loss = (sum_losses / loss_count) if loss_count > 0 else 0

    best_trade = max(trades, key=lambda t: t["pnl"])
    worst_trade = min(trades, key=lambda t: t["pnl"])
    avg_pnl = total_pnl / total_trades
    avg_hold = sum(t["hold_days"] for t in trades) / total_trades
    avg_dte = sum(t["dte"] for t in trades) / total_trades

    # Date range
    all_dates = sorted(set(t["exit_date"][:10] for t in trades) | set(t["entry_date"][:10] for t in trades))
    min_date, max_date = all_dates[0], all_dates[-1]
    d1 = _parse_date(min_date)
    d2 = _parse_date(max_date)
    period_days = (d2 - d1).days + 1 if d1 and d2 else 0
    date_range_str = f"{d1.strftime('%d %b %Y')} - {d2.strftime('%d %b %Y')}" if d1 and d2 else ""

    unique_underlyings = set(t["underlying"] for t in trades)

    metadata = {
        "filename": filename,
        "date_range": date_range_str,
        "total_trades": total_trades,
        "total_symbols": len(unique_underlyings),
        "period_days": period_days,
    }

    # ── Tab 1: Overview ──
    # Equity curve (deduplicated by date, keep running total)
    trades_by_exit = sorted(trades, key=lambda t: t["exit_date"])
    cum_pnl = 0
    ec_dict = {}
    for t in trades_by_exit:
        cum_pnl += t["pnl"]
        ec_dict[t["exit_date"][:10]] = round(cum_pnl, 2)
    equity_curve = [{"date": d, "cumulative_pnl": v} for d, v in sorted(ec_dict.items())]

    # Monthly P&L
    monthly_groups = defaultdict(list)
    for t in trades_by_exit:
        monthly_groups[t["exit_date"][:7]].append(t)

    monthly_pnl = []
    cum_monthly = 0
    for month_key in sorted(monthly_groups.keys()):
        group = monthly_groups[month_key]
        m_pnl = sum(t["pnl"] for t in group)
        cum_monthly += m_pnl
        monthly_pnl.append({
            "month": month_key, "pnl": round(m_pnl, 2),
            "trade_count": len(group), "cumulative": round(cum_monthly, 2),
        })

    overview = {
        "total_pnl": round(total_pnl, 2),
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "best_trade": {"pnl": round(best_trade["pnl"], 2), "underlying": best_trade["underlying"]},
        "worst_trade": {"pnl": round(worst_trade["pnl"], 2), "underlying": worst_trade["underlying"]},
        "avg_pnl_per_trade": round(avg_pnl, 2),
        "avg_holding_period": round(avg_hold, 1),
        "avg_dte": round(avg_dte, 1),
        "winners": win_count,
        "losers": loss_count,
        "avg_winner": round(avg_win, 2),
        "avg_loser": round(avg_loss, 2),
        "win_loss_ratio": round(avg_win / avg_loss, 2) if avg_loss > 0 else 0,
        "equity_curve": equity_curve,
        "monthly_pnl": monthly_pnl,
    }

    # ── Tab 2: P&L Analysis ──
    pnl_analysis = _compute_pnl_analysis(trades, monthly_groups)

    # ── Tab 3: Instrument Analysis ──
    instrument_analysis = _compute_instrument_analysis(trades)

    # ── Tab 4: Expiry Analysis ──
    expiry_analysis = _compute_expiry_analysis(trades)

    # ── Tab 5: Risk Metrics ──
    risk_metrics = _compute_risk_metrics(trades, equity_curve, total_pnl, win_rate, avg_win, avg_loss, profit_factor)

    # ── Tab 6: Trade Log ──
    trade_log = {"completed_trades": trades, "open_positions": open_positions}

    return {
        "report_type": "csv",
        "metadata": metadata,
        "overview": overview,
        "pnl_analysis": pnl_analysis,
        "instrument_analysis": instrument_analysis,
        "expiry_analysis": expiry_analysis,
        "risk_metrics": risk_metrics,
        "trade_log": trade_log,
    }


# ─── Tab 2: P&L Analysis ─────────────────────────────────────────────────────

def _compute_pnl_analysis(trades, monthly_groups):
    monthly_table = []
    for month_key in sorted(monthly_groups.keys()):
        group = monthly_groups[month_key]
        m_pnl = sum(t["pnl"] for t in group)
        m_wins = [t for t in group if t["pnl"] > 0]
        m_losses = [t for t in group if t["pnl"] <= 0]
        m_capital = sum(t["capital"] for t in group)
        m_sum_wins = sum(t["pnl"] for t in m_wins)
        m_sum_losses = abs(sum(t["pnl"] for t in m_losses))
        m_pf = (m_sum_wins / m_sum_losses) if m_sum_losses > 0 else (999.99 if m_sum_wins > 0 else 0)

        monthly_table.append({
            "month": month_key,
            "trades": len(group),
            "gross_pnl": round(m_pnl, 2),
            "pnl_pct": round((m_pnl / m_capital * 100) if m_capital > 0 else 0, 2),
            "win_rate": round((len(m_wins) / len(group) * 100) if group else 0, 2),
            "avg_pnl": round(m_pnl / len(group), 2) if group else 0,
            "largest_win": round(max((t["pnl"] for t in group), default=0), 2),
            "largest_loss": round(min((t["pnl"] for t in group), default=0), 2),
            "profit_factor": round(m_pf, 2),
        })

    # Daily heatmap
    daily_groups = defaultdict(float)
    for t in trades:
        daily_groups[t["exit_date"][:10]] += t["pnl"]
    daily_heatmap = [{"date": d, "pnl": round(v, 2)} for d, v in sorted(daily_groups.items())]

    # Day of week
    dow_groups = defaultdict(list)
    for t in trades:
        dt = _parse_date(t["exit_date"])
        if dt and dt.weekday() < 5:
            dow_groups[WEEKDAY_NAMES[dt.weekday()]].append(t)

    day_of_week = []
    for day_name in WEEKDAY_NAMES:
        group = dow_groups.get(day_name, [])
        if not group:
            day_of_week.append({"day": day_name, "avg_pnl": 0, "total_pnl": 0, "win_rate": 0, "trade_count": 0})
            continue
        d_pnl = sum(t["pnl"] for t in group)
        d_wins = sum(1 for t in group if t["pnl"] > 0)
        day_of_week.append({
            "day": day_name,
            "avg_pnl": round(d_pnl / len(group), 2),
            "total_pnl": round(d_pnl, 2),
            "win_rate": round(d_wins / len(group) * 100, 2),
            "trade_count": len(group),
        })

    trades_per_day = [{"day": d["day"], "count": d["trade_count"]} for d in day_of_week]

    return {
        "monthly_table": monthly_table,
        "daily_heatmap": daily_heatmap,
        "day_of_week": day_of_week,
        "trades_per_day": trades_per_day,
    }


# ─── Tab 3: Instrument Analysis ──────────────────────────────────────────────

def _compute_instrument_analysis(trades):
    futures = [t for t in trades if t["instrument_type"] == "FUT"]
    ces = [t for t in trades if t["instrument_type"] == "CE"]
    pes = [t for t in trades if t["instrument_type"] == "PE"]
    index_trades = [t for t in trades if t["is_index"]]
    stock_trades = [t for t in trades if not t["is_index"]]

    summary_cards = {
        "futures_pnl": round(sum(t["pnl"] for t in futures), 2), "futures_count": len(futures),
        "ce_pnl": round(sum(t["pnl"] for t in ces), 2), "ce_count": len(ces),
        "pe_pnl": round(sum(t["pnl"] for t in pes), 2), "pe_count": len(pes),
        "index_pnl": round(sum(t["pnl"] for t in index_trades), 2), "index_count": len(index_trades),
        "stock_pnl": round(sum(t["pnl"] for t in stock_trades), 2), "stock_count": len(stock_trades),
    }

    # Per-underlying table
    und_groups = defaultdict(list)
    for t in trades:
        und_groups[t["underlying"]].append(t)

    per_underlying = []
    for und, group in und_groups.items():
        u_pnl = sum(t["pnl"] for t in group)
        u_capital = sum(t["capital"] for t in group)
        u_wins = sum(1 for t in group if t["pnl"] > 0)
        per_underlying.append({
            "underlying": und,
            "trades": len(group),
            "total_pnl": round(u_pnl, 2),
            "pnl_pct": round((u_pnl / u_capital * 100) if u_capital > 0 else 0, 2),
            "win_rate": round(u_wins / len(group) * 100, 2),
            "avg_return": round(sum(t["pnl_pct"] for t in group) / len(group), 2),
            "capital": round(u_capital, 2),
        })
    per_underlying.sort(key=lambda x: abs(x["total_pnl"]), reverse=True)

    # Top 5 winners / losers
    by_pnl = sorted(per_underlying, key=lambda x: x["total_pnl"], reverse=True)
    top5_winners = [{"underlying": u["underlying"], "pnl": u["total_pnl"]} for u in by_pnl[:5]]
    top5_losers = [{"underlying": u["underlying"], "pnl": u["total_pnl"]} for u in by_pnl[-5:]]

    # Capital concentration
    total_cap = sum(u["capital"] for u in per_underlying) or 1
    cap_sorted = sorted(per_underlying, key=lambda x: x["capital"], reverse=True)[:10]
    capital_concentration = [
        {"underlying": u["underlying"], "capital": u["capital"], "pct": round(u["capital"] / total_cap * 100, 2)}
        for u in cap_sorted
    ]

    # Directional analysis
    longs = [t for t in trades if t["direction"] == "long"]
    shorts = [t for t in trades if t["direction"] == "short"]
    directional = {
        "long_pnl": round(sum(t["pnl"] for t in longs), 2),
        "short_pnl": round(sum(t["pnl"] for t in shorts), 2),
        "long_trades": len(longs),
        "short_trades": len(shorts),
        "long_win_rate": round(sum(1 for t in longs if t["pnl"] > 0) / len(longs) * 100, 2) if longs else 0,
        "short_win_rate": round(sum(1 for t in shorts if t["pnl"] > 0) / len(shorts) * 100, 2) if shorts else 0,
    }

    # Long vs short by underlying (top 20)
    ls_by_und = defaultdict(lambda: {"long_pnl": 0, "short_pnl": 0})
    for t in trades:
        if t["direction"] == "long":
            ls_by_und[t["underlying"]]["long_pnl"] += t["pnl"]
        else:
            ls_by_und[t["underlying"]]["short_pnl"] += t["pnl"]

    ls_list = sorted([
        {"underlying": u, "long_pnl": round(v["long_pnl"], 2), "short_pnl": round(v["short_pnl"], 2),
         "net_pnl": round(v["long_pnl"] + v["short_pnl"], 2)}
        for u, v in ls_by_und.items()
    ], key=lambda x: abs(x["net_pnl"]), reverse=True)[:20]

    return {
        "summary_cards": summary_cards,
        "per_underlying": per_underlying,
        "top5_winners": top5_winners,
        "top5_losers": top5_losers,
        "capital_concentration": capital_concentration,
        "directional": directional,
        "long_short_by_underlying": ls_list,
    }


# ─── Tab 4: Expiry Analysis ──────────────────────────────────────────────────

def _compute_expiry_analysis(trades):
    monthly_trades = [t for t in trades if t["is_monthly"]]
    weekly_trades = [t for t in trades if t["is_weekly"]]

    def _stats(group):
        if not group:
            return {"pnl": 0, "trades": 0, "win_rate": 0, "avg_return": 0}
        g_pnl = sum(t["pnl"] for t in group)
        g_wins = sum(1 for t in group if t["pnl"] > 0)
        return {
            "pnl": round(g_pnl, 2), "trades": len(group),
            "win_rate": round(g_wins / len(group) * 100, 2),
            "avg_return": round(sum(t["pnl_pct"] for t in group) / len(group), 2),
        }

    # P&L by expiry date
    expiry_groups = defaultdict(list)
    for t in trades:
        if t["expiry_date"]:
            expiry_groups[t["expiry_date"]].append(t)

    pnl_by_expiry = []
    for exp_date in sorted(expiry_groups.keys()):
        group = expiry_groups[exp_date]
        e_pnl = sum(t["pnl"] for t in group)
        e_wins = sum(1 for t in group if t["pnl"] > 0)
        pnl_by_expiry.append({
            "expiry_date": exp_date, "pnl": round(e_pnl, 2), "trades": len(group),
            "win_rate": round(e_wins / len(group) * 100, 2),
            "avg_pnl": round(e_pnl / len(group), 2),
        })

    # DTE buckets: 0, 1-3, 4-7, 7+
    dte_defs = [("0 DTE", 0, 0), ("1-3 DTE", 1, 3), ("4-7 DTE", 4, 7), ("7+ DTE", 8, 99999)]
    dte_buckets = []
    for name, lo, hi in dte_defs:
        group = [t for t in trades if lo <= t["dte"] <= hi]
        if not group:
            dte_buckets.append({"bucket": name, "pnl": 0, "trades": 0, "win_rate": 0})
            continue
        b_pnl = sum(t["pnl"] for t in group)
        b_wins = sum(1 for t in group if t["pnl"] > 0)
        dte_buckets.append({
            "bucket": name, "pnl": round(b_pnl, 2), "trades": len(group),
            "win_rate": round(b_wins / len(group) * 100, 2),
        })

    return {
        "monthly_vs_weekly": {"monthly": _stats(monthly_trades), "weekly": _stats(weekly_trades)},
        "pnl_by_expiry": pnl_by_expiry,
        "dte_buckets": dte_buckets,
    }


# ─── Tab 5: Risk Metrics ─────────────────────────────────────────────────────

def _compute_risk_metrics(trades, equity_curve, total_pnl, win_rate, avg_win, avg_loss, profit_factor):
    total_trades = len(trades)
    winners = [t for t in trades if t["pnl"] > 0]
    losers = [t for t in trades if t["pnl"] <= 0]
    sum_wins = sum(t["pnl"] for t in winners)
    sum_losses = abs(sum(t["pnl"] for t in losers))

    payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0
    expectancy = total_pnl / total_trades if total_trades > 0 else 0

    # Max drawdown
    peak = 0
    max_dd = 0
    max_dd_pct = 0
    drawdown_curve = []
    for pt in equity_curve:
        val = pt["cumulative_pnl"]
        if val > peak:
            peak = val
        dd = peak - val
        dd_pct = (dd / peak * 100) if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd_pct
        drawdown_curve.append({"date": pt["date"], "drawdown_pct": round(dd_pct, 2)})

    recovery_factor = (total_pnl / max_dd) if max_dd > 0 else 0

    # Consecutive wins/losses
    max_cw = 0
    max_cl = 0
    cw = 0
    cl = 0
    for t in trades:
        if t["pnl"] > 0:
            cw += 1
            cl = 0
            max_cw = max(max_cw, cw)
        else:
            cl += 1
            cw = 0
            max_cl = max(max_cl, cl)

    # Sharpe ratio (annualized from daily P&L)
    daily_pnl_map = defaultdict(float)
    for t in trades:
        daily_pnl_map[t["exit_date"][:10]] += t["pnl"]
    daily_pnls = list(daily_pnl_map.values())

    sharpe = 0
    if len(daily_pnls) > 1:
        mean_d = sum(daily_pnls) / len(daily_pnls)
        var_d = sum((x - mean_d) ** 2 for x in daily_pnls) / (len(daily_pnls) - 1)
        std_d = math.sqrt(var_d) if var_d > 0 else 0
        if std_d > 0:
            sharpe = (mean_d / std_d) * math.sqrt(252)

    cards = {
        "profit_factor": round(profit_factor, 2),
        "payoff_ratio": round(payoff_ratio, 2),
        "expectancy": round(expectancy, 2),
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "max_consec_wins": max_cw,
        "max_consec_losses": max_cl,
        "sharpe_ratio": round(sharpe, 2),
        "recovery_factor": round(recovery_factor, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "total_wins": round(sum_wins, 2),
        "total_losses": round(sum_losses, 2),
    }

    # Histograms
    pnl_vals = [t["pnl"] for t in trades]
    pct_vals = [t["pnl_pct"] for t in trades]

    # Risk-reward scatter
    scatter = [{"capital": round(t["capital"], 2), "pnl": round(t["pnl"], 2),
                "symbol": t["symbol"], "underlying": t["underlying"]} for t in trades]

    return {
        "cards": cards,
        "pnl_distribution": _make_histogram(pnl_vals, 12),
        "return_pct_distribution": _make_histogram(pct_vals, 12),
        "risk_reward_scatter": scatter,
        "drawdown_curve": drawdown_curve,
    }


def _make_histogram(values, num_bins):
    if not values:
        return []
    min_val = min(values)
    max_val = max(values)
    if min_val == max_val:
        return [{"range": f"{min_val:.0f}", "count": len(values), "min": min_val, "max": max_val}]
    bin_width = (max_val - min_val) / num_bins
    bins = []
    for i in range(num_bins):
        lo = min_val + i * bin_width
        hi = min_val + (i + 1) * bin_width
        count = sum(1 for v in values if (lo <= v < hi) or (i == num_bins - 1 and v == hi))
        bins.append({"range": f"{lo:.0f} to {hi:.0f}", "count": count, "min": round(lo, 2), "max": round(hi, 2)})
    return bins


# ─── Empty Response ───────────────────────────────────────────────────────────

def _empty_response(filename, open_positions=None):
    return {
        "report_type": "csv",
        "metadata": {"filename": filename, "date_range": "", "total_trades": 0, "total_symbols": 0, "period_days": 0},
        "overview": {
            "total_pnl": 0, "total_trades": 0, "win_rate": 0, "profit_factor": 0,
            "best_trade": {"pnl": 0, "underlying": "-"}, "worst_trade": {"pnl": 0, "underlying": "-"},
            "avg_pnl_per_trade": 0, "avg_holding_period": 0, "avg_dte": 0,
            "winners": 0, "losers": 0, "avg_winner": 0, "avg_loser": 0, "win_loss_ratio": 0,
            "equity_curve": [], "monthly_pnl": [],
        },
        "pnl_analysis": {"monthly_table": [], "daily_heatmap": [], "day_of_week": [], "trades_per_day": []},
        "instrument_analysis": {
            "summary_cards": {"futures_pnl": 0, "futures_count": 0, "ce_pnl": 0, "ce_count": 0,
                              "pe_pnl": 0, "pe_count": 0, "index_pnl": 0, "index_count": 0,
                              "stock_pnl": 0, "stock_count": 0},
            "per_underlying": [], "top5_winners": [], "top5_losers": [], "capital_concentration": [],
            "directional": {"long_pnl": 0, "short_pnl": 0, "long_trades": 0, "short_trades": 0,
                            "long_win_rate": 0, "short_win_rate": 0},
            "long_short_by_underlying": [],
        },
        "expiry_analysis": {
            "monthly_vs_weekly": {
                "monthly": {"pnl": 0, "trades": 0, "win_rate": 0, "avg_return": 0},
                "weekly": {"pnl": 0, "trades": 0, "win_rate": 0, "avg_return": 0},
            },
            "pnl_by_expiry": [], "dte_buckets": [],
        },
        "risk_metrics": {
            "cards": {"profit_factor": 0, "payoff_ratio": 0, "expectancy": 0, "max_drawdown": 0,
                      "max_drawdown_pct": 0, "max_consec_wins": 0, "max_consec_losses": 0,
                      "sharpe_ratio": 0, "recovery_factor": 0, "avg_win": 0, "avg_loss": 0,
                      "total_wins": 0, "total_losses": 0},
            "pnl_distribution": [], "return_pct_distribution": [],
            "risk_reward_scatter": [], "drawdown_curve": [],
        },
        "trade_log": {"completed_trades": [], "open_positions": open_positions or []},
    }


# ─── HTTP Handler ─────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" not in content_type:
            self._json_response(400, {"error": "Expected multipart/form-data"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Extract boundary
        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[len("boundary="):].strip('"')
                break

        if not boundary:
            self._json_response(400, {"error": "No boundary in multipart data"})
            return

        # Parse multipart
        boundary_bytes = ("--" + boundary).encode()
        parts = body.split(boundary_bytes)

        file_bytes = None
        filename = "unknown.csv"
        for part in parts:
            if b"Content-Disposition" in part and b"filename=" in part:
                header_end = part.find(b"\r\n\r\n")
                if header_end == -1:
                    continue
                header_section = part[:header_end].decode("utf-8", errors="replace")
                fn_match = re.search(r'filename="([^"]+)"', header_section)
                if fn_match:
                    filename = fn_match.group(1)
                file_content = part[header_end + 4:]
                if file_content.endswith(b"\r\n"):
                    file_content = file_content[:-2]
                if file_content.endswith(b"--\r\n"):
                    file_content = file_content[:-4]
                file_bytes = file_content
                break

        if file_bytes is None:
            self._json_response(400, {"error": "No file found in upload"})
            return

        if not filename.lower().endswith(".csv"):
            self._json_response(400, {"error": "Only .csv files are accepted"})
            return

        try:
            csv_text = file_bytes.decode("utf-8", errors="replace")
            executions = parse_csv(csv_text)

            if not executions:
                self._json_response(422, {"error": "No valid trade executions found in CSV"})
                return

            trades, open_positions = match_trades(executions)
            result = compute_all(trades, open_positions, filename)
            self._json_response(200, result)

        except Exception as e:
            self._json_response(422, {"error": f"Failed to analyze CSV: {str(e)}"})

    def do_GET(self):
        self._json_response(200, {"status": "ok", "service": "trade-nexus-csv-analyzer"})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json_response(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
