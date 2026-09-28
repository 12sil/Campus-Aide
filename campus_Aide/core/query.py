"""只读查询层：只消费快照，不引入任何写入方法。

查询页面只调用本模块读取业务数据，课程/项目、具体任务与任务分配的写入由服务层负责。
"""
from decimal import Decimal
from core.rules import warning


def enriched_orders(data, today=None):
    """使用稳定外键双向关联；同时保留入单时的名称快照便于历史审计。"""
    customers = {c["id"]: c for c in data["customers"]}
    products = {p["id"]: p for p in data["products"]}
    result = []
    for row in data["orders"]:
        x = dict(row)
        x["current_customer"] = customers.get(x["customer_id"], {}).get("name", x["customer_name"])
        x["current_product"] = products.get(x["product_id"], {}).get("name", x["product_name"])
        x.update(warning(x["delivery_deadline"], x["status"], today))
        result.append(x)
    return sorted(result, key=lambda r: (r["rank"], r["ship_date"], r["id"]))


def customer_trace(data, customer_id, today=None):
    return [o for o in enriched_orders(data, today) if o["customer_id"] == customer_id]


def product_trace(data, product_id, today=None):
    return [o for o in enriched_orders(data, today) if o["product_id"] == product_id]


def order_history(data, ids):
    """包含每次状态变化和执行记录，即使后来回退也保留原记录。"""
    return sorted([dict(h) for h in data["history"] if h["order_id"] in ids], key=lambda h: h["created_at"], reverse=True)


def shipped_summary(data, month):
    """按实际启动月份，课程/项目、具体任务单位分别累计，绝不把件数与重量相加。"""
    summary = {}
    for o in enriched_orders(data):
        if o["status"] not in ("已启动", "已完成") or not o["shipped_date"].startswith(month):
            continue
        key = (o["customer_id"], o["unit"])
        if key not in summary:
            summary[key] = {"课程/项目": o["current_customer"], "单位": o["unit"], "启动任务分配数": 0, "启动数量": Decimal(0)}
        summary[key]["启动任务分配数"] += 1
        summary[key]["启动数量"] += Decimal(o["quantity"])
    return [{**row, "启动数量": format(row["启动数量"], "f")} for row in summary.values()]
