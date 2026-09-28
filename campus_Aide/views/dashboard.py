"""板块二：智能启动预警。预警清单独立于月份筛选，防止跨月漏单。"""
import streamlit as st
import pandas as pd
import plotly.express as px
from core.rules import today_china
from core.query import enriched_orders, shipped_summary
from core.service import update_status
from views.common import header, order_table, saved, notify


def render(store):
    header("02 / TASK ALERTS", "智能任务分配预警看板", "任务截止日期 − 3 个自然日 = 必须启动日期。")
    notify()
    data = store.read()
    orders = enriched_orders(data)
    # 顶部三个数字按全部月份的未启动任务分配统计，三类互斥，避免重复计数。
    high, near, safe = st.columns(3)
    high.metric("🔴 急（今天必须开始做）", sum(o["level"] in ("overdue", "today") for o in orders))
    near.metric("🟡 缓冲（这几天做就行）", sum(o["level"] == "urgent" for o in orders))
    safe.metric("🟢 不急（本周内完成即可）", sum(o["level"] == "normal" for o in orders))
    st.caption("全部月份 · 仅未启动：急 = 逾期或今日必须启动；缓冲 = 1～3 天内必须启动；不急 = 超过 3 天。")
    st.caption("不急为安排建议：优先在本周推进；实际截止日以任务日期为准。已启动任务仍可在总览中跟踪。")
    st.markdown("#### 📊 任务分配预警分布概览")
    chart = pd.DataFrame({"任务分配数量": [
        sum(o["level"] in ("overdue", "today") for o in orders),
        sum(o["level"] == "urgent" for o in orders),
        sum(o["level"] == "normal" for o in orders),
    ]}, index=["急", "缓冲", "不急"])
    st.bar_chart(chart, y="任务分配数量", color="#66c7e8", height=260)
    # 与数字看板使用相同口径；无未启动任务分配时不绘制误导性的空圆环。
    ring_col, trend_col = st.columns(2)
    with ring_col:
        st.markdown("#### 红黄绿 · 预警状态占比")
        if chart["任务分配数量"].sum():
            fig = px.pie(chart.reset_index(names="状态"), names="状态", values="任务分配数量",
                         hole=.65, color="状态", color_discrete_map={
                             "急": "#f39a8f", "缓冲": "#f4c879", "不急": "#83d6a8"})
            fig.update_traces(textinfo="label+percent", hovertemplate="%{label}：%{value} 笔<extra></extra>")
            fig.update_layout(height=320, margin=dict(l=15, r=15, t=20, b=20),
                              paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig, use_container_width=True, key="risk_ring")
        else:
            st.info("暂无未启动任务分配。")
    with trend_col:
        st.markdown("#### 月度任务分配分布")
        # 按交付月份统计任务分配笔数；补齐中间空月份，跨年也按日期排序。
        active = [o for o in orders if o["status"] != "已取消"]
        st.caption("按任务截止月份统计任务分配笔数，排除已取消任务分配；不受下方月份筛选影响。")
        if active:
            counts = pd.Series([o["order_month"] for o in active]).value_counts().sort_index()
            months_all = pd.period_range(counts.index.min(), counts.index.max(), freq="M").astype(str)
            trend = counts.reindex(months_all, fill_value=0).rename_axis("月份").reset_index(name="任务分配笔数")
            fig = px.line(trend, x="月份", y="任务分配笔数", markers=True,
                          color_discrete_sequence=["#a99bea"])
            fig.update_xaxes(type="category")
            fig.update_yaxes(rangemode="tozero", dtick=1)
            fig.update_layout(height=320, margin=dict(l=15, r=15, t=20, b=20),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True, key="monthly_trend")
        else:
            st.info("暂无可统计任务分配。")
    today = today_china()
    left, right = st.columns([3, 1])
    with left:
        st.info(f"📅 北京时间 {today.isoformat()}　｜　准备预留 3 天　｜　任务分配月按任务截止月份归属")
    with right:
        if st.button("刷新预警", use_container_width=True):
            st.rerun()
    months = sorted({today.strftime("%Y-%m")} | {o["order_month"] for o in orders}, reverse=True)
    month = st.selectbox("全月任务分配总览 · 选择月份", months, index=months.index(today.strftime("%Y-%m")))
    monthly = [o for o in orders if o["order_month"] == month]
    due = [o for o in orders if o["level"] == "today"]
    urgent = [o for o in orders if o["level"] == "urgent"]
    late = [o for o in orders if o["level"] == "overdue"]
    a, b, c, d = st.columns(4)
    a.metric("本月任务分配总数", len(monthly))
    b.metric("今日必须启动 · 全部月份", len(due))
    c.metric("3 天内缓冲任务 · 全部月份", len(urgent))
    d.metric("启动逾期 · 全部月份", len(late))
    st.subheader("🔴 今日必须启动清单")
    st.caption("独立清单，包含全部月份。未启动且今天等于系统计算启动日，必须今天开始。")
    order_table(due, "今天没有必须启动的任务分配。")
    if due:
        with st.expander("今日任务分配 · 一键确认已启动"):
            for order in due:
                text, action = st.columns([4, 1])
                text.write(f"{order['current_customer']} · {order['current_product']} · {order['quantity']} {order['unit']}")
                if action.button("确认已启动", key=f"ship_{order['id']}", use_container_width=True):
                    try:
                        update_status(store, order["id"], "已启动", today, note="今日清单一键确认启动", expected_status="未启动")
                        saved("已记录实际启动日期；该任务分配已移出未启动预警。")
                    except ValueError as exc:
                        st.error(str(exc))
    with st.expander(f"🔴 已错过启动日 · 今天立即开始 · {len(late)} 笔", expanded=bool(late)):
        order_table(late, "没有启动逾期任务分配。")
    with st.expander(f"🟡 缓冲待启动清单 · {len(urgent)} 笔", expanded=True):
        st.caption("距离必须启动日为 1、2、3 天；今日与逾期任务分配在各自清单展示。")
        order_table(urgent, "未来 3 天暂无缓冲任务任务分配。")
    st.divider()
    st.subheader(f"{month} · 全月任务分配总览")
    q = st.text_input("筛选本月任务分配", placeholder="课程/项目 / 具体任务 / 具体任务编码 / 任务分配编号")
    filtered = [o for o in monthly if q.casefold() in " ".join((o["current_customer"], o["current_product"], o["product_code"], o["id"])).casefold()]
    order_table(filtered, "所选月份没有匹配任务分配。")
    with st.expander("课程/项目月度启动统计 · 按实际启动月份"):
        summary = shipped_summary(data, month)
        if summary:
            st.dataframe(summary, hide_index=True, use_container_width=True)
        else:
            st.info("该月还没有实际启动记录。")
        st.caption("以实际启动日期统计，已取消任务分配排除；不同计量单位分开汇总。")

