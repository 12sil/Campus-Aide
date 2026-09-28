"""基础课程/项目档案维护，独立于只读追溯页面。"""
import streamlit as st
from core.service import save_customer
from views.common import header, notify, saved


def render(store):
    header("COURSES / PROJECTS", "课程/项目档案管理", "统一课程/项目档案，以稳定编号关联所有具体任务与任务分配。")
    notify()
    data = store.read()
    query = st.text_input("搜索课程/项目档案", placeholder="课程/项目名称 / 负责人 / 电话")
    rows = [c for c in data["customers"] if query.casefold() in " ".join((c["name"], c["contact"], c["phone"])).casefold()]
    st.metric("课程/项目档案总数", len(data["customers"]))
    if rows:
        st.dataframe([{"课程/项目编号": c["id"], "课程/项目名称": c["name"], "负责人": c["contact"], "电话": c["phone"], "上课 / 活动地点": c["address"]} for c in rows], hide_index=True, use_container_width=True)
    mode = st.radio("档案操作", ["新增课程/项目", "修改课程/项目"], horizontal=True)
    row = {}
    if mode == "修改课程/项目":
        if not data["customers"]:
            st.info("暂无可修改课程/项目。")
            return
        row = st.selectbox("选择课程/项目档案", data["customers"], format_func=lambda c: c["name"])
    with st.form("customer_form"):
        a, b = st.columns(2)
        values = {}
        values["name"] = a.text_input("课程/项目名称 *", row.get("name", ""), max_chars=100)
        values["contact"] = b.text_input("负责人", row.get("contact", ""), max_chars=100)
        values["phone"] = a.text_input("联系电话", row.get("phone", ""), max_chars=50)
        values["address"] = b.text_input("上课 / 活动地点", row.get("address", ""), max_chars=500)
        values["notes"] = st.text_area("档案备注", row.get("notes", ""), max_chars=2000)
        submit = st.form_submit_button("保存课程/项目档案", type="primary")
    if submit:
        try:
            save_customer(store, values, row.get("id"))
            saved("课程/项目档案已保存，历史关联保持不变。")
        except ValueError as exc:
            st.error(str(exc))

