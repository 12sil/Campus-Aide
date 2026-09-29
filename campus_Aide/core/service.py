"""业务服务层：课程/项目/具体任务关联、任务分配入库、状态变更与导入去重。

所有写操作集中在本文件；查询页面仅调用 core.query，不暴露修改入口。
采用稳定 ID 关联，改名不会造成课程/项目与任务分配断开。
"""
from pathlib import Path
from decimal import Decimal
import hashlib
import io
import json
import os
import re
import uuid
from PIL import Image, ImageOps
from config import STATUSES
from core.rules import parse_date, quantity_text, required_ship_date, timestamp, today_china


def uid(prefix):
    return prefix + uuid.uuid4().hex[:16]


def add_campus_task(store, title, group_name, deadline, notes=''):
    """课程、任务与计划一次提交，避免新增流程留下孤立档案。"""
    title = clean(title, '任务名称', 100, True)
    group_name = clean(group_name, '课程或活动名称', 100, True)
    with store.transaction() as data:
        group = next((g for g in data['customers'] if normalize(g['name']) == normalize(group_name)), None)
        if group is None:
            group = dict(id=uid('C'), name=group_name, contact='', phone='', address='', notes='', created_at=timestamp())
            data['customers'].append(group)
        task = dict(id=uid('P'), name=title, code=uid('TASK-'), unit='项', description=notes,
                    specs='', checklist='', bom='', image_path='', created_at=timestamp())
        data['products'].append(task)
        return _add_order(data, dict(customer_id=group['id'], product_id=task['id'], quantity=1,
                                    delivery_deadline=deadline, notes=notes))


def clean(value, label, limit=3000, required=False):
    """服务层再次校验，不能只依靠网页组件的 required 限制。"""
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"请填写{label}。")
    if len(text) > limit:
        raise ValueError(f"{label}不能超过 {limit} 字。")
    return text


def normalize(value):
    return re.sub(r"\s+", "", str(value)).casefold()


def save_customer(store, values, customer_id=None):
    name = clean(values.get("name"), "课程/项目名称", 100, True)
    with store.transaction() as data:
        if any(normalize(x["name"]) == normalize(name) and x["id"] != customer_id for x in data["customers"]):
            raise ValueError("同名课程/项目已经存在，请打开原档案修改。")
        if customer_id:
            row = next((x for x in data["customers"] if x["id"] == customer_id), None)
            if row is None:
                raise ValueError("课程/项目不存在，请刷新页面。")
        else:
            row = {"id": uid("C"), "created_at": timestamp()}
            data["customers"].append(row)
        row.update({"name": name, "contact": clean(values.get("contact"), "负责人", 100),
                    "phone": clean(values.get("phone"), "电话", 50),
                    "address": clean(values.get("address"), "地址", 500),
                    "notes": clean(values.get("notes"), "备注", 2000)})
        return row["id"]


def save_product(store, values, product_id=None):
    name = clean(values.get("name"), "具体任务名称", 100, True)
    code = clean(values.get("code"), "具体任务编码", 100, True)
    with store.transaction() as data:
        if any(normalize(x["code"]) == normalize(code) and x["id"] != product_id for x in data["products"]):
            raise ValueError("具体任务编码已存在，请修改编码或编辑原具体任务。")
        if product_id:
            row = next((x for x in data["products"] if x["id"] == product_id), None)
            if row is None:
                raise ValueError("具体任务不存在，请刷新页面。")
        else:
            row = {"id": uid("P"), "created_at": timestamp()}
            data["products"].append(row)
        row.update({"name": name, "code": code, "unit": clean(values.get("unit"), "计量单位", 15, True),
                    "description": clean(values.get("description"), "具体任务介绍", 6000),
                    "specs": clean(values.get("specs"), "任务要求", 6000),
                    "checklist": clean(values.get("checklist"), "检查表", 6000),
                    "bom": clean(values.get("bom"), "任务步骤与资源清单", 12000),
                    "image_path": clean(values.get("image_path"), "图片路径", 500)})
        return row["id"]


def save_image(store, raw):
    """解码后重新编码为 PNG，防止假图片；图片字节保存在附件目录，路径存 CSV。"""
    if len(raw) > 10 * 1024 * 1024:
        raise ValueError("具体任务图片不能超过 10 MB。")
    try:
        image = Image.open(io.BytesIO(raw))
        if image.width * image.height > 24000000:
            raise ValueError("图片像素过大，请压缩后上传。")
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1600, 1600))
        output = io.BytesIO()
        image.save(output, format="PNG")
    except (OSError, Image.DecompressionBombError):
        raise ValueError("无法读取图片，请上传有效 PNG/JPG/WebP 图片。") from None
    content = output.getvalue()
    relative = f"uploads/products/{hashlib.sha256(content).hexdigest()}.png"
    path = store.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return relative


def _add_order(data, values, source="手动录入", source_file="", import_key=""):
    """内部方法：在已经持有事务锁时使用，方便多个识别任务分配一次提交。"""
    customer = next((x for x in data["customers"] if x["id"] == values.get("customer_id")), None)
    product = next((x for x in data["products"] if x["id"] == values.get("product_id")), None)
    if not customer or not product:
        raise ValueError("课程/项目或具体任务不存在，请先建立档案。")
    deadline = parse_date(values.get("delivery_deadline"))
    if not 2000 <= deadline.year <= 2100:
        raise ValueError("任务截止日期年份必须在 2000 至 2100 之间。")
    row = {"id": uid("O"), "customer_id": customer["id"], "product_id": product["id"],
           "customer_name": customer["name"], "product_name": product["name"],
           "product_code": product["code"], "unit": product["unit"],
           "quantity": quantity_text(values.get("quantity")),
           # 任务分配月定义为任务截止日期所在月，跨月启动仍会出现在全局预警清单。
           "order_month": deadline.strftime("%Y-%m"), "delivery_deadline": deadline.isoformat(),
           "ship_due_date": required_ship_date(deadline).isoformat(), "status": "未启动",
           "shipped_date": "", "delivered_date": "", "source": source, "source_file": source_file,
           "import_key": import_key, "notes": clean(values.get("notes"), "任务分配备注", 2000),
           "created_at": timestamp(), "updated_at": timestamp()}
    data["orders"].append(row)
    data["history"].append({"id": uid("H"), "order_id": row["id"], "from_status": "", "to_status": "未启动",
                            "shipped_date": "", "delivered_date": "", "note": f"建立任务分配：{source}", "created_at": timestamp()})
    return row["id"]


def create_order(store, values):
    with store.transaction() as data:
        return _add_order(data, values)


def update_status(store, order_id, new_status, shipped_date=None, delivered_date=None, note="", expected_status=None):
    """状态转换与日期同步保存。重复确认不重复启动，回退需要说明并保留历史。"""
    if new_status not in STATUSES:
        raise ValueError("任务分配状态不合法。")
    with store.transaction() as data:
        row = next((x for x in data["orders"] if x["id"] == order_id), None)
        if row is None:
            raise ValueError("任务分配不存在。")
        old = row["status"]
        if expected_status is not None and old != expected_status:
            raise ValueError("任务分配已被其他会话修改，请刷新后再操作。")
        if new_status == old:
            return
        note = clean(note, "变更说明", 2000)
        normal = {("未启动", "已启动"), ("已启动", "已完成")}
        if (old, new_status) not in normal and not note:
            raise ValueError("取消、跳级或回退状态必须填写变更说明。")
        ship, delivered = "", ""
        if new_status in ("已启动", "已完成"):
            ship = parse_date(shipped_date or row["shipped_date"] or today_china()).isoformat()
            if parse_date(ship) > today_china():
                raise ValueError("实际启动日期不能晚于今天。")
        if new_status == "已完成":
            delivered = parse_date(delivered_date or today_china()).isoformat()
            if parse_date(delivered) < parse_date(ship) or parse_date(delivered) > today_china():
                raise ValueError("实际完成日必须在实际启动日与今天之间。")
        row.update(status=new_status, shipped_date=ship, delivered_date=delivered, updated_at=timestamp())
        data["history"].append({"id": uid("H"), "order_id": order_id, "from_status": old, "to_status": new_status,
                                "shipped_date": ship, "delivered_date": delivered, "note": note, "created_at": timestamp()})


def import_orders(store, rows, file_hash, file_name, raw_bytes, engine, raw_text):
    """识别入单：同一文件哈希只入库一次；新课程/项目/具体任务和任务分配在同一事务提交。

    匹配优先具体任务编码，其次精确具体任务名；同名不同版本不会擅自合并。
    """
    if not rows:
        raise ValueError("没有可导入任务分配。")
    if len(rows) > 100:
        raise ValueError("单次最多导入 100 行任务分配。")
    suffix = Path(file_name).suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".webp", ".pdf"):
        raise ValueError("不支持的任务分配附件格式。")
    path = store.root / "uploads" / "orders" / f"{file_hash}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    with store.transaction() as data:
        previous = next((x for x in data["imports"] if x["file_hash"] == file_hash), None)
        if previous:
            raise ValueError("该文件已成功导入，系统已阻止重复入单。")
        result = []
        for i, item in enumerate(rows):
            customer_name = clean(item.get("customer_name"), "识别课程/项目名称", 100, True)
            product_name = clean(item.get("product_name"), "识别具体任务名称", 100, True)
            candidates = [x for x in data["customers"] if normalize(x["name"]) == normalize(customer_name)]
            if len(candidates) > 1:
                raise ValueError("课程/项目名称存在歧义，请先检查档案。")
            if candidates:
                customer = candidates[0]
            else:
                customer = {"id": uid("C"), "name": customer_name, "contact": "", "phone": "", "address": "", "notes": "由任务分配识别建立，课程资料待补充。", "created_at": timestamp()}
                data["customers"].append(customer)
            code = clean(item.get("product_code"), "识别具体任务编码", 100)
            matches = [x for x in data["products"] if normalize(x["code"] if code else x["name"]) == normalize(code or product_name)]
            if len(matches) > 1:
                raise ValueError(f"具体任务“{product_name}”存在多个版本，请在识别结果中补充具体任务编码。")
            if matches:
                product = matches[0]
                if code and normalize(product["name"]) != normalize(product_name):
                    raise ValueError(f"编码 {code} 对应具体任务“{product['name']}”，与识别名称不一致，请核对。")
                if item.get("unit") and normalize(item["unit"]) != normalize(product["unit"]):
                    raise ValueError(f"{product_name} 的识别单位与资料库不一致，请核对。")
            else:
                product = {"id": uid("P"), "code": code or "AI-" + uuid.uuid4().hex[:10].upper(), "name": product_name,
                           "unit": clean(item.get("unit") or "项", "单位", 15, True), "description": "由任务分配识别建立，具体任务资料待补充。",
                           "specs": "", "checklist": "", "bom": "", "image_path": "", "created_at": timestamp()}
                data["products"].append(product)
            result.append(_add_order(data, {"customer_id": customer["id"], "product_id": product["id"], "quantity": item.get("quantity"),
                                            "delivery_deadline": item.get("delivery_deadline"), "notes": "文件识别入单"},
                                     source=f"智能导入 · {engine}", source_file=str(path.relative_to(store.root)), import_key=f"{file_hash}:{i}"))
        # 附件先写入，任务分配快照后提交；失败时最多留下无引用附件，不会有缺失附件的任务分配。
        temp = path.with_name(path.name + ".tmp")
        temp.write_bytes(raw_bytes)
        os.replace(temp, path)
        data["imports"].append({"id": uid("I"), "file_hash": file_hash, "file_name": Path(file_name).name,
                                "engine": engine, "order_ids": ";".join(result), "raw_text": raw_text[:50000], "created_at": timestamp()})
        return result

