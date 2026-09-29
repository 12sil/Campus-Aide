"""校园场景演示数据，永远不写入正式业务空间。"""
from datetime import timedelta
from core.rules import timestamp, today_china
from core.service import _add_order, uid


def reset_demo_orders(store):
    """用五条虚构任务分配替换当前任务分配；相对今天生成日期，比赛当天也能展示预警。

    配置依次为：课程/项目序号、具体任务序号、数量、距离必须启动日的天数。
    可在此修改五条样例；任务截止日始终等于必须启动日加三天。
    """
    samples = [(0, 0, 1, -1), (1, 1, 1, 0), (2, 2, 1, 1),
               (3, 3, 1, 3), (1, 1, 1, 8)]
    today = today_china()
    with store.transaction() as data:
        # 保留档案；只重置任务分配相关表，避免残留历史记录指向旧任务分配。
        data["orders"] = []
        data["history"] = []
        data["imports"] = []
        for customer, product, quantity, offset in samples:
            _add_order(data, {
                "customer_id": data["customers"][customer % len(data["customers"])]["id"],
                "product_id": data["products"][product % len(data["products"])]["id"],
                "quantity": quantity,
                "delivery_deadline": today + timedelta(days=offset + 3),
                "notes": "一键加载的虚构演示任务分配",
            }, source="演示数据")


def seed_demo(store):
    """只在全新演示空间首次创建，同一会话内刷新保留修改；新会话重新初始化。"""
    with store.transaction() as data:
        if any(data.values()):
            return
        customers = [("互联网+创新创业比赛", "项目负责人", "", "大学生活动中心"),
                     ("高等数学（下）", "学习委员", "", "东区教学楼"),
                     ("英语四级备考计划", "自我管理", "", "图书馆"),
                     ("学生会宣传部", "部门负责人", "", "社团活动室")]
        for name, contact, phone, address in customers:
            data["customers"].append({"id": uid("C"), "name": name, "contact": contact, "phone": phone, "address": address, "notes": "校园演示课程/项目", "created_at": timestamp()})
        products = [("TASK-01", "互联网+比赛项目书", "项", "完成商业计划书、路演材料与答辩演练。", "组队：4-6 人\n提交：PDF + 演示文稿", "确定选题 | 指导老师意见 | 完成路演彩排"),
                    ("TASK-02", "写高数作业", "项", "完成本周高等数学章节习题并整理错题。", "范围：第 5 章 1-30 题\n提交：纸质作业", "独立完成 | 错题订正 | 课前提交"),
                    ("TASK-03", "准备四级考试", "项", "制定听力、阅读和写作的复习安排。", "目标：四级考试\n材料：真题 3 套", "完成一套真题 | 复盘错题 | 背诵作文模板"),
                    ("TASK-04", "社团策划案", "项", "完成社团招新活动策划案与预算表。", "字数：1500 字以上\n协作：宣传部", "活动流程 | 预算核对 | 指导老师审核")]
        for code, name, unit, desc, specs, bom in products:
            data["products"].append({"id": uid("P"), "code": code, "name": name, "unit": unit, "description": desc,
                                     "specs": specs, "bom": bom, "checklist": "核对任务要求\n完成初稿或练习\n复查并提交", "image_path": "", "created_at": timestamp()})
        # offset 指必须启动日相对今天；任务截止日必须再加 3 天。
        for i, offset in enumerate((0, 0, 1, 3, -2, 8, 12, -4)):
            today = today_china()
            oid = _add_order(data, {"customer_id": data["customers"][i % 4]["id"], "product_id": data["products"][i % 4]["id"],
                                    "quantity": 1,
                                    "delivery_deadline": today + timedelta(days=offset + 3), "notes": "校园演示任务分配"}, source="演示数据")
            if i == 7:
                row = next(o for o in data["orders"] if o["id"] == oid)
                row.update(status="已完成", shipped_date=(today - timedelta(days=4)).isoformat(), delivered_date=(today - timedelta(days=1)).isoformat())
                data["history"].append({"id": uid("H"), "order_id": oid, "from_status": "未启动", "to_status": "已完成", "shipped_date": row["shipped_date"],
                                        "delivered_date": row["delivered_date"], "note": "演示历史执行记录", "created_at": timestamp()})

