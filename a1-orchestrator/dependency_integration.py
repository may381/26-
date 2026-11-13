"""整合 P2 已验收并过滤后的子任务快照，不重新执行子任务。"""

from p2_client import P2Error

TERMINAL = {"SUCCEEDED", "PARTIALLY_SUCCEEDED", "FAILED", "CANCELLED", "EXPIRED"}


def integrate_dependencies(root_task_id, dependencies):
    if not isinstance(dependencies, list) or not dependencies or len(dependencies) > 6:
        raise P2Error("dependencyResults 数量无效")
    lines, results = [], []
    successes = failures = partials = 0
    domains = []
    for item in dependencies:
        if (not isinstance(item, dict) or item.get("parentTaskId") != root_task_id
                or not isinstance(item.get("taskId"), str) or not item["taskId"]
                or item.get("status") not in TERMINAL
                or type(item.get("required")) is not bool):
            raise P2Error("子任务快照无效或不属于当前根任务")
        domain = item.get("domain")
        if isinstance(domain, str) and domain and domain not in domains:
            domains.append(domain)
        status = item["status"]
        reply = item.get("reply")
        text = reply.get("text") if isinstance(reply, dict) else None
        label = domain or item.get("targetAgent") or "协作任务"
        if status == "SUCCEEDED":
            successes += 1
            lines.append("%s：%s" % (label, text if isinstance(text, str) and text.strip() else "已完成"))
        elif status == "PARTIALLY_SUCCEEDED":
            partials += 1
            lines.append("%s：%s" % (label, text if isinstance(text, str) and text.strip() else "部分完成"))
        else:
            failures += 1
            error = item.get("error")
            message = error.get("message") if isinstance(error, dict) else None
            lines.append("%s：未完成%s" % (label, "（%s）" % message if isinstance(message, str) and message else ""))
        cards = item.get("results", [])
        if not isinstance(cards, list) or not all(isinstance(card, dict) for card in cards):
            raise P2Error("子任务结果卡格式无效")
        if len(results) + len(cards) > 20:
            raise P2Error("子任务结果卡超过单次返回上限")
        results.extend(cards)
    if failures and not (successes or partials):
        outcome = "FAILED"
    elif failures or partials:
        outcome = "PARTIALLY_SUCCEEDED"
    else:
        outcome = "SUCCEEDED"
    reply = "\n".join(lines)
    if len(reply) > 1500:
        reply = reply[:1497] + "…"
    return {"outcome": outcome, "reply": reply, "results": results, "domains": domains}


def collect_child_confirmations(root_task_id, dependencies):
    if not isinstance(dependencies, list) or not dependencies or len(dependencies) > 6:
        raise P2Error("待确认子任务快照数量无效")
    confirmation_ids, domains = [], []
    for item in dependencies:
        if (not isinstance(item, dict) or item.get("parentTaskId") != root_task_id
                or item.get("status") != "WAITING_CONFIRMATION"):
            raise P2Error("待确认子任务快照无效或不属于当前根任务")
        values = item.get("confirmationIds")
        if (not isinstance(values, list) or not values
                or not all(isinstance(value, str) and 0 < len(value) <= 128 for value in values)):
            raise P2Error("子任务没有有效confirmationIds")
        for value in values:
            if value not in confirmation_ids:
                confirmation_ids.append(value)
        domain = item.get("domain")
        if isinstance(domain, str) and domain and domain not in domains:
            domains.append(domain)
    if len(confirmation_ids) > 20:
        raise P2Error("待确认操作超过单次展示上限")
    return {"confirmationIds": confirmation_ids, "domains": domains}

