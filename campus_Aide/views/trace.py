"""板块一：双向关联查询。仅展示，不保存、不修改任何业务数据。"""
import streamlit as st
import pandas as pd
from decimal import Decimal
from core.query import customer_trace, product_trace, order_history
from views.common import header, order_table, history_table, product_details


def render(store):
    header("01 / TRACEABILITY", "双向数据查询", "课程/项目 → 具体任务 → 任务分配；具体任务 → 课程/项目 → 历史记录。此页面为纯查询。")
    data = store.read()
    keyword = st.text_input("快速检索", placeholder="输入课程/项目名称、具体任务名称或具体任务编码")
    tab_c, tab_p = st.tabs(["👥 从课程/项目追溯", "📚 从具体任务反查"])
    with tab_c:
        customers = [c for c in data["customers"] if not keyword or keyword.casefold() in c["name"].casefold()]
        if not customers:
            st.info("没有匹配课程/项目，请调整检索内容或先建立课程/项目档案。")
        else:
            selected = st.selectbox("选择课程/项目", customers, format_func=lambda c: c["name"], key="trace_customer")
            st.write(f"负责人：{selected['contact'] or '未填写'}  |  电话：{selected['phone'] or '未填写'}")
            st.caption(f"上课 / 活动地点：{selected['address'] or '未填写'}")
            orders = customer_trace(data, selected["id"])
            a, b, c = st.columns(3)
            a.metric("历史任务分配", len(orders))
            b.metric("分配具体任务种类", len({o["product_id"] for o in orders}))
            c.metric("涉及任务分配月份", len({o["order_month"] for o in orders}))
            st.subheader("所有历史任务分配")
            order_table(orders)
            st.markdown("#### 📊 课程/项目各具体任务分配数量")
            st.caption("汇总该课程/项目历史任务分配数量，排除已取消任务分配；不同单位分开展示。")
            # 使用具体任务 ID 与单位分组，避免同名具体任务或不同计量单位混加。
            totals = {}
            for order in orders:
                if order["status"] == "已取消":
                    continue
                key = (order["product_id"], order["unit"])
                if key not in totals:
                    totals[key] = {"具体任务": f"{order['current_product']} · {order['product_code']}",
                                   "单位": order["unit"], "分配数量": Decimal(0)}
                totals[key]["分配数量"] += Decimal(order["quantity"])
            if totals:
                frame = pd.DataFrame([{**row, "分配数量": float(row["分配数量"])} for row in totals.values()])
                for unit, group in frame.groupby("单位", sort=False):
                    st.caption(f"计量单位：{unit}")
                    st.bar_chart(group.set_index("具体任务")[["分配数量"]], color="#3158dd", height=280)
            else:
                st.info("该课程/项目暂无可统计的分配数量。")
            # 具体任务展开详情与具体任务反查共用同一份资料，避免数据割裂。
            with st.expander("查看该课程/项目涉及的具体任务资料"):
                ids = {o["product_id"] for o in orders}
                for product in data["products"]:
                    if product["id"] in ids:
                        product_details(product, store)
                        st.divider()
            with st.expander("执行与状态追溯记录"):
                history_table(order_history(data, {o["id"] for o in orders}))
    with tab_p:
        products = [p for p in data["products"] if not keyword or keyword.casefold() in (p["name"] + p["code"]).casefold()]
        if not products:
            st.info("没有匹配具体任务，请调整检索内容或先建立具体任务资料。")
        else:
            selected = st.selectbox("选择具体任务", products, format_func=lambda p: f"{p['code']} · {p['name']}", key="trace_product")
            orders = product_trace(data, selected["id"])
            st.markdown("#### 哪些课程/项目关联过？")
            ids = {o["customer_id"] for o in orders}
            customers = [c for c in data["customers"] if c["id"] in ids]
            if customers:
                st.dataframe([{"课程/项目": c["name"], "负责人": c["contact"], "电话": c["phone"],
                               "历史任务分配数": sum(o["customer_id"] == c["id"] for o in orders)} for c in customers],
                              hide_index=True, use_container_width=True)
            else:
                st.info("该具体任务暂无分配记录。")
            st.subheader("该具体任务的所有历史任务分配")
            order_table(orders)
            with st.expander("执行与状态追溯记录", expanded=False):
                history_table(order_history(data, {o["id"] for o in orders}))
            with st.expander("查看具体任务全套资料"):
                product_details(selected, store)
