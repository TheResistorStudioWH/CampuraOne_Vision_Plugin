"""Deterministic, provider-independent scenario calculator. No network or video I/O."""
import heapq
import itertools
import math
from datetime import datetime, timezone


class InputError(ValueError):
    pass


def number(value, name, low=0, high=10000, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(name + " 必须是数字")
    if not math.isfinite(value) or not low <= value <= high:
        raise InputError("%s 必须在 %s–%s 范围内" % (name, low, high))
    if integer and value != int(value):
        raise InputError(name + " 必须是整数")
    return int(value) if integer else float(value)


def obj(value, name):
    if not isinstance(value, dict):
        raise InputError(name + " 必须是对象")
    return value


def sequence(value, name, limit=2000):
    if not isinstance(value, list) or len(value) > limit:
        raise InputError(name + " 必须是长度不超过 %d 的数组" % limit)
    return value


def timestamp(value):
    if not isinstance(value, str):
        raise InputError("时间必须是带时区的 ISO 8601 字符串")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except ValueError:
        raise InputError("时间必须是带时区的 ISO 8601 字符串")


def stamp(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def freshness(value, now, ttl, name):
    if value is None:
        return name + "缺失"
    obj(value, name)
    if "observed_at" not in value:
        return name + "缺少更新时间"
    age = (now - timestamp(value["observed_at"])).total_seconds()
    if age < -5:
        return name + "时间在未来，需核对时钟"
    if age > ttl:
        return name + "已过期（有效期 %s 秒）" % ttl
    return None


def bounds(value, name, high=10):
    items = sequence(value, name, 2)
    if len(items) != 2:
        raise InputError(name + " 需要 [下限, 上限]")
    lo, hi = [number(x, name, high=high) for x in items]
    if lo > hi:
        raise InputError(name + " 下限不能大于上限")
    return lo, hi


def interval(values):
    if not values:
        return None
    # Outward rounding avoids narrowing a scenario envelope.
    return [math.floor((min(values) + 1e-9) * 10) / 10,
            math.ceil((max(values) - 1e-9) * 10) / 10]


def card(label, values=None, reasons=None, parts=None, basis=None, status=None):
    reasons = reasons or []
    return {"label": label,
            "status": status or ("scenario" if values else "partial" if parts else "unavailable"),
            "minutes": interval(values), "reasons": reasons,
            "parts": parts or {}, "basis": basis or []}


def schedule(available, arrival, duration):
    free = heapq.heappop(available)
    finish = max(free, arrival) + duration
    heapq.heappush(available, finish)
    return finish


def periodic(rate, horizon):
    """Synthetic arrivals: first arrival at 1/rate; not a stochastic guarantee."""
    if rate == 0:
        return []
    return [i / rate for i in range(1, int(math.floor(rate * horizon + 1e-9)) + 1)]


def crowd_band(ratio):
    if ratio is None:
        return "unknown"
    return "low" if ratio < 0.25 else "medium" if ratio < 0.60 else "high"


def selection_range(calibration, now, band):
    prior = (1.0, 6.0)
    issue = freshness(calibration, now, 7 * 86400, "挑选时长样本")
    if issue:
        return prior, issue + "；使用 1–6 分钟工程初值，未按本店校准", 0
    samples = sequence(calibration.get("samples"), "calibration.samples", 500)
    selected = []
    for sample in samples:
        obj(sample, "sample")
        minutes = number(sample.get("minutes"), "sample.minutes", 0.1, 60)
        ratio = number(sample.get("space_occupancy_ratio"), "sample.space_occupancy_ratio", 0, 1)
        if band != "unknown" and crowd_band(ratio) == band:
            selected.append(minutes)
    if len(selected) < 30:
        return prior, "同拥挤档样本不足 30 个；使用 1–6 分钟工程初值，未按本店校准", len(selected)
    selected.sort()

    def quantile(p):
        index = (len(selected) - 1) * p
        low = int(index)
        high = min(low + 1, len(selected) - 1)
        return selected[low] + (selected[high] - selected[low]) * (index - low)

    return (quantile(0.1), quantile(0.9)), "最近同拥挤档匿名模拟样本 P10–P90；不是实店准确率或置信区间", len(selected)


def ledger(snapshot, now, slots):
    issue = freshness(snapshot, now, 60, "订单快照")
    if issue:
        return [], issue
    if snapshot.get("complete") is not True:
        return [], "订单快照不完整，无法确认所有积压订单"
    latest = {}
    observed = timestamp(snapshot["observed_at"])
    for event in sequence(snapshot.get("events"), "orders.events"):
        obj(event, "order event")
        key = event.get("id")
        if not isinstance(key, str) or not key or len(key) > 100:
            raise InputError("订单 id 必须是 1–100 字符的字符串")
        status = event.get("status")
        if status is None:
            return [], "订单记录缺少状态"
        if status not in ("pending", "accepted", "preparing", "ready", "cancelled"):
            raise InputError("未知订单状态")
        placed = timestamp(event.get("placed_at"))
        updated = timestamp(event.get("updated_at"))
        accepted = timestamp(event["accepted_at"]) if event.get("accepted_at") else None
        ready = timestamp(event["ready_at"]) if event.get("ready_at") else None
        if placed > updated or updated > observed:
            raise InputError("订单事件时间顺序错误，或晚于快照")
        if status in ("accepted", "preparing", "ready") and accepted is None:
            raise InputError("已确认订单必须提供 accepted_at")
        if accepted and not placed <= accepted <= updated:
            raise InputError("accepted_at 必须位于下单与更新时间之间")
        if ready and (accepted is None or not accepted <= ready <= updated):
            raise InputError("ready_at 时间顺序错误")
        if status == "preparing" and event.get("remaining_minutes") is None:
            return [], "正在制作的订单缺少剩余制作时间"
        remaining = (number(event["remaining_minutes"], "remaining_minutes", 0, 60)
                     if status == "preparing" else None)
        normalized = {"id": key, "status": status, "placed": placed, "accepted": accepted,
                      "updated": updated, "ready": ready, "remaining": remaining}
        old = latest.get(key)
        if old and old["updated"] == updated and old != normalized:
            return [], "同一订单的同时间事件互相冲突"
        if old is None or old["updated"] < updated:
            latest[key] = normalized
    result = list(latest.values())
    if sum(o["status"] == "preparing" for o in result) > slots:
        return [], "正在制作订单数超过并行工位数"
    return result, None


def kitchen(orders, slots, duration, factor, future=()):
    preparing = [o for o in orders if o["status"] == "preparing"]
    available = [o["remaining"] * factor for o in preparing] + [0.0] * (slots - len(preparing))
    heapq.heapify(available)
    finish = {o["id"]: o["remaining"] * factor for o in preparing}
    waiting = sorted((o for o in orders if o["status"] == "accepted"),
                     key=lambda o: (o["accepted"], o["id"]))
    for order in waiting:
        finish[order["id"]] = schedule(available, 0, duration * factor)
    for arrival in sorted(future):
        schedule(available, arrival, duration * factor)
    return available, finish


def queue_state(value, now, slots, scope):
    issue = freshness(value, now, 30, "交易队伍")
    if issue:
        return None, issue
    if value.get("scope") != scope or value.get("unit") != "transactions":
        return None, "需要单独的待办交易队伍；不能将画面人数直接当作订单"
    waiting = number(value.get("waiting"), "service_queue.waiting", 0, 500, integer=True)
    remaining = value.get("busy_remaining_minutes")
    if remaining is None:
        return None, "缺少点单或收银工位当前服务进度"
    busy = [number(x, "busy_remaining_minutes", 0, 10)
            for x in sequence(remaining, "busy_remaining_minutes", slots)]
    return (waiting, busy), None


def counter(queue, slots, duration, factor, arrivals, target_arrival):
    waiting, busy = queue
    available = [x * factor for x in busy] + [0.0] * (slots - len(busy))
    heapq.heapify(available)
    completed = [x * factor for x in busy]
    for _ in range(waiting):
        completed.append(schedule(available, 0, duration * factor))
    for arrival in arrivals:
        completed.append(schedule(available, arrival, duration * factor))
    target_done = schedule(available, target_arrival, duration * factor)
    # A job on another counter can complete after the target.
    return target_done, [x for x in completed if x <= target_done]


def estimate(data, now=None):
    obj(data, "input")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1 or data.get("mode") != "simulation":
        raise InputError("仅支持 schema_version=1、mode=simulation")
    if data.get("kind") not in ("dining", "retail"):
        raise InputError("kind 必须为 dining 或 retail")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise InputError("计算时钟必须带时区")
    kind = data["kind"]
    capacity = obj(data.get("capacity"), "capacity")
    variation = number(capacity.get("variation", 0.2), "capacity.variation", 0, 0.5)
    factors = sorted(set((1 - variation, 1 + variation)))
    arrival = data.get("arrival_minutes")
    if arrival is not None:
        arrival = number(arrival, "arrival_minutes", 0, 120)

    vision = data.get("vision")
    vision_issue = freshness(vision, now, 30, "视觉汇总")
    coverage, ratio, occupancy, people = [], None, None, None
    scene = "unconfirmed"
    if vision is not None:
        coverage = sequence(vision.get("coverage", []), "vision.coverage", 10)
        if any(x not in ("entrance", "shopping", "checkout", "ordering") for x in coverage):
            raise InputError("未知覆盖区域")
        scene = vision.get("scene", "unconfirmed")
        if scene not in ("queue", "whole_store", "unconfirmed"):
            raise InputError("未知画面类型")
        for key in ("occupancy", "queue_people"):
            if vision.get(key) is not None:
                value = number(vision[key], "vision." + key, 0, 10000, integer=True)
                if key == "occupancy":
                    occupancy = value
                else:
                    people = value
        if vision.get("space_occupancy_ratio") is not None:
            ratio = number(vision["space_occupancy_ratio"], "space_occupancy_ratio", 0, 1)
    band = crowd_band(ratio) if not vision_issue else "unknown"
    views = data.get("page_views")
    view_issue = freshness(views, now, 60, "页面浏览人数")
    active_views = (number(views.get("active_people"), "page_views.active_people", 0, 1000000, True)
                    if views is not None else None)
    forecast = data.get("forecast")
    forecast_issue = freshness(forecast, now, 60, "未来需求情景")
    if forecast is not None and forecast.get("basis") != "simulation":
        raise InputError("此版本的未来需求必须明确标记 basis=simulation")
    warnings = ["所有输入均为模拟数据；区间是情景包络，不是统计置信区间。",
                "页面浏览人数、店内人数未直接折算订单；没有本店转化记录。",
                "一次待办交易视为一单，需独立提供交易队伍，不能从原始人数直接相加。"]
    if vision_issue:
        warnings.append(vision_issue)
    if view_issue:
        warnings.append(view_issue + "；未用于数值计算")
    result = {
        "schema_version": 1, "mode": "simulation", "kind": kind, "calculated_at": stamp(now),
        "source_updated_at": {key: data[key].get("observed_at") if isinstance(data.get(key), dict) else None
                              for key in ("vision", "orders", "service_queue", "forecast", "page_views", "calibration")},
        "travel_minutes": arrival,
        "counts": {"occupancy": occupancy, "queue_people": people, "vision_state": vision_issue or "fresh",
                   "active_page_viewers": active_views, "views_state": view_issue or "fresh"},
        "congestion": {"band": band, "space_occupancy_ratio": ratio,
                       "basis": "模拟可用地面占用比例；阈值未按本店校准，与人数和 ETA 分开"},
        "warnings": warnings,
    }
    service_name = "order" if kind == "dining" else "checkout"
    service_minutes = capacity.get(service_name + "_minutes")
    service_slots = capacity.get(service_name + "_slots")
    queue = None
    if service_minutes is None or service_slots is None:
        queue_issue = "缺少点单或收银处理能力"
    else:
        service_minutes = number(service_minutes, service_name + "_minutes", 0.05, 10)
        service_slots = number(service_slots, service_name + "_slots", 1, 20, True)
        queue, queue_issue = queue_state(data.get("service_queue"), now, service_slots,
                                         "ordering" if kind == "dining" else "checkout")
    if kind == "dining":
        prep = capacity.get("prep_minutes")
        slots = capacity.get("prep_slots")
        orders, order_issue = [], "缺少制作能力"
        if prep is not None and slots is not None:
            prep = number(prep, "prep_minutes", 0.1, 60)
            slots = number(slots, "prep_slots", 1, 50, True)
            orders, order_issue = ledger(data.get("orders"), now, slots)
        result["backlog"] = None if order_issue else sum(o["status"] in ("accepted", "preparing") for o in orders)
        result["preorder"] = preorder(data.get("preorder_order_id"), orders, order_issue,
                                      slots, prep, factors, now)
        rates = None
        if not forecast_issue:
            if "online_orders_per_minute" not in forecast or "walk_in_orders_per_minute" not in forecast:
                forecast_issue = "缺少线上或到店新增需求情景"
            else:
                rates = (bounds(forecast["online_orders_per_minute"], "online_orders_per_minute"),
                         bounds(forecast["walk_in_orders_per_minute"], "walk_in_orders_per_minute"))

        def arrival_at(a):
            label = "现在到店后等待" if a == 0 else "预计到店后等待"
            reasons = [x for x in (order_issue, queue_issue, forecast_issue, vision_issue) if x]
            if scene == "unconfirmed" or "ordering" not in coverage:
                reasons.append("点单区域不可见或画面用途未确认")
            parts = {}
            if not order_issue:
                parts["立即确认一张新订单的制作时间"] = result["preorder"].get("new_order_minutes")
            if queue is not None and (a == 0 or rates is not None):
                qtimes = []
                for f, rate in itertools.product(factors, rates[1] if rates else (0,)):
                    end, _ = counter(queue, service_slots, service_minutes, f, periodic(rate, a), a)
                    qtimes.append(end - a)
                parts["排队及点单"] = interval(qtimes)
            if reasons:
                return card(label, reasons=reasons, parts={k: v for k, v in parts.items() if v is not None})
            totals, making, ordering = [], [], []
            for pf, qf, online, walk_in in itertools.product(factors, factors, *rates):
                accepted, walk_orders = counter(queue, service_slots, service_minutes, qf,
                                                 periodic(walk_in, a), a)
                if accepted > 120:
                    return card(label, reasons=["点单结束超出 120 分钟预测窗口"], parts=parts)
                future = periodic(online, accepted) + walk_orders
                available, _ = kitchen(orders, slots, prep, pf, future)
                ready = schedule(available, accepted, prep * pf)
                totals.append(ready - a)
                making.append(ready - accepted)
                ordering.append(accepted - a)
            return card(label, totals, parts={"排队及点单": interval(ordering),
                                              "下单后制作": interval(making)},
                        basis=["统一先确认先制作；已在制作订单使用剩余时长",
                               "未来线上订单与点单队伍分开模拟；目标确认后到达的订单不插队",
                               "路程只改变到达时店况，不计入到店后等待"])
    else:
        selected, note, sample_count = selection_range(data.get("calibration"), now, band)
        result["selection"] = {"minutes": interval(selected), "basis": note, "matching_samples": sample_count}
        result["preorder"] = card("零售线上预订", reasons=["第一版不提供零售预订时间"], status="not_supported")
        checkout_rates = None
        if not forecast_issue:
            if "checkout_arrivals_per_minute" not in forecast:
                forecast_issue = "缺少未来进入收银队伍的需求情景"
            else:
                checkout_rates = bounds(forecast["checkout_arrivals_per_minute"], "checkout_arrivals_per_minute")

        def arrival_at(a):
            label = "现在进店至结账完成" if a == 0 else "预计进店至结账完成"
            reasons = [x for x in (queue_issue, forecast_issue, vision_issue) if x]
            missing = set(("entrance", "shopping", "checkout")) - set(coverage)
            if missing:
                reasons.append("单机位未覆盖：" + "、".join(sorted(missing)))
            if scene == "unconfirmed":
                reasons.append("画面用途未确认")
            parts = {"挑选时间（工程初值或模拟样本）": interval(selected)}
            totals, checkout = [], []
            if queue is not None and checkout_rates is not None:
                for s, f, rate in itertools.product(selected, factors, checkout_rates):
                    if a + s > 120:
                        reasons.append("走到收银台的时刻超出 120 分钟预测窗口")
                        continue
                    end, _ = counter(queue, service_slots, service_minutes, f,
                                     periodic(rate, a + s), a + s)
                    checkout.append(end - a - s)
                    totals.append(end - a)
                if checkout and "checkout" in coverage and not vision_issue and scene != "unconfirmed":
                    parts["挑选后排队及结账"] = interval(checkout)
            if reasons:
                return card(label, reasons=list(dict.fromkeys(reasons)), parts=parts)
            return card(label, totals, parts=parts, basis=[note,
                        "推演挑选结束时的队伍；当前队伍不会原封不动叠加到未来",
                        "拥挤只用于匹配样本，未编造固定拥挤倍数"])
    result["arrival_now"] = arrival_at(0)
    result["arrival_route"] = (arrival_at(arrival) if arrival is not None
                               else card("预计到店后等待", reasons=["缺少地图路程时间"]))
    return result


def preorder(target_id, orders, issue, slots, prep, factors, now):
    if issue:
        return card("餐饮预订", reasons=[issue])
    values, new_values, remaining = [], [], []
    target = next((o for o in orders if o["id"] == target_id), None) if target_id is not None else None
    for factor in factors:
        available, finish = kitchen(orders, slots, prep, factor)
        new_values.append(schedule(available, 0, prep * factor))
        if target and target["status"] in ("accepted", "preparing"):
            remaining.append(finish[target_id])
            values.append((now - target["placed"]).total_seconds() / 60 + finish[target_id])
    if target_id is not None and target is None:
        answer = card("餐饮预订", reasons=["指定订单不在完整快照中"])
    elif target and target["status"] == "pending":
        answer = card("餐饮预订", reasons=["待商家确认；尚不输出订单 ETA"], status="pending")
    elif target and target["status"] == "cancelled":
        answer = card("餐饮预订", reasons=["订单已取消"], status="cancelled")
    elif target and target["status"] == "ready":
        actual = [(target["ready"] - target["placed"]).total_seconds() / 60] if target["ready"] else None
        answer = card("餐饮预订", actual, reasons=[] if actual else ["已可取餐，缺少实际可取时间"],
                      parts={"从现在还需等待": [0, 0]}, status="ready")
    else:
        answer = card("餐饮预订" if target else "现在预订并立即确认（试算）",
                      values if target else new_values,
                      parts={"从现在还需等待": interval(remaining if target else new_values)},
                      basis=["从原下单时刻到可取餐；无关顾客是否到店",
                             "未下单的试算假设立即确认；实际未确认订单只显示待确认"])
    answer["new_order_minutes"] = interval(new_values)
    return answer
