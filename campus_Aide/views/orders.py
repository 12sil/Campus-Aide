"""任务管理辅助页面：与只读追溯分离，提供人工入单和状态修改。"""
import streamlit as st
from core.rules import today_china, required_ship_date, parse_date
from core.query import enriched_orders, order_history
from core.service import create_order, update_status
from config import STATUSES
from views.common import header, order_table, history_table, notify, saved


def render(store):
    header("PLAN / HISTORY", "调整任务状态", "取消、恢复或更正计划状态，保留每次变更记录。")
    notify()
    data = store.read()
    orders = enriched_orders(data)
    if not orders:
        st.info("暂无任务。")
    else:
        order = st.selectbox("选择要更新的任务", orders, format_func=lambda o: f"{o['id']} · {o['current_customer']} · {o['current_product']} · {o['status']}")
        order_table([order])
        target = st.selectbox("新状态", STATUSES, index=STATUSES.index(order["status"]))
        with st.form("change_status"):
            ship, arrival = None, None
            if target in ("已启动", "已完成"):
                ship = st.date_input("实际启动日期", value=parse_date(order["shipped_date"]) if order["shipped_date"] else today_china(), max_value=today_china())
            if target == "已完成":
                arrival = st.date_input("实际完成日期", value=parse_date(order["delivered_date"]) if order["delivered_date"] else today_china(), max_value=today_china())
            note = st.text_area("变更说明", placeholder="取消、回退或跳级必须说明原因，所有变化均保留追溯记录。")
            submit = st.form_submit_button("更新任务状态", type="primary")
        if submit:
            try:
                update_status(store, order["id"], target, ship, arrival, note, expected_status=order["status"])
                saved("状态已更新，追溯记录已保存。")
            except ValueError as exc:
                st.error(str(exc))
        with st.expander("该任务完整执行记录"):
            history_table(order_history(data, {order["id"]}))

