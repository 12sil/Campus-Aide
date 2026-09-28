"""任务分配管理辅助页面：与只读追溯分离，提供人工入单和状态修改。"""
import streamlit as st
from core.rules import today_china, required_ship_date, parse_date
from core.query import enriched_orders, order_history
from core.service import create_order, update_status
from config import STATUSES
from views.common import header, order_table, history_table, notify, saved


def render(store):
    header("TASK OPERATIONS", "手动任务分配与状态管理", "录入任务截止日期，系统自动回推必须启动日期。")
    notify()
    data = store.read()
    first, second = st.tabs(["＋ 手动新增任务分配", "↻ 修改任务分配状态"])
    with first:
        if not data["customers"] or not data["products"]:
            st.info("请先到基础资料页面新增课程/项目和具体任务，再录入任务分配。")
        else:
            # 日期放在表单之外，日期变动立即更新启动日预览。
            deadline = st.date_input("任务截止日期", value=today_china(), min_value=parse_date("2000-01-04"), max_value=parse_date("2100-12-31"))
            st.info(f"系统计算必须启动日：{required_ship_date(deadline).isoformat()}　｜　任务分配月：{deadline:%Y-%m}")
            with st.form("manual_order", clear_on_submit=True):
                customer = st.selectbox("课程/项目", data["customers"], format_func=lambda c: c["name"])
                product = st.selectbox("具体任务", data["products"], format_func=lambda p: f"{p['code']} · {p['name']}（{p['unit']}）")
                qty = st.number_input("任务分配数量", min_value=0.001, max_value=100000000.0, value=1.0, step=1.0, format="%.3f")
                notes = st.text_area("任务分配备注", max_chars=2000)
                submit = st.form_submit_button("保存任务分配", type="primary", use_container_width=True)
            if submit:
                try:
                    order_id = create_order(store, {"customer_id": customer["id"], "product_id": product["id"], "quantity": qty, "delivery_deadline": deadline, "notes": notes})
                    saved(f"任务分配 {order_id} 已保存到当前演示会话，默认状态为未启动。")
                except ValueError as exc:
                    st.error(str(exc))
    with second:
        orders = enriched_orders(data)
        if not orders:
            st.info("暂无任务分配。")
        else:
            order = st.selectbox("选择要更新的任务分配", orders, format_func=lambda o: f"{o['id']} · {o['current_customer']} · {o['current_product']} · {o['status']}")
            order_table([order])
            target = st.selectbox("新状态", STATUSES, index=STATUSES.index(order["status"]))
            with st.form("change_status"):
                ship, arrival = None, None
                if target in ("已启动", "已完成"):
                    ship = st.date_input("实际启动日期", value=parse_date(order["shipped_date"]) if order["shipped_date"] else today_china(), max_value=today_china())
                if target == "已完成":
                    arrival = st.date_input("实际完成日期", value=parse_date(order["delivered_date"]) if order["delivered_date"] else today_china(), max_value=today_china())
                note = st.text_area("变更说明", placeholder="取消、回退或跳级必须说明原因，所有变化均保留追溯记录。")
                submit = st.form_submit_button("更新任务分配状态", type="primary")
            if submit:
                try:
                    update_status(store, order["id"], target, ship, arrival, note, expected_status=order["status"])
                    saved("状态已更新，追溯记录已保存。")
                except ValueError as exc:
                    st.error(str(exc))
            with st.expander("该任务分配完整执行记录"):
                history_table(order_history(data, {order["id"]}))

