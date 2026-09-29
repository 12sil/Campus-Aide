"""校园智汇 · Streamlit 主入口。

运行：python -m streamlit run app.py
主入口仅负责导航、样式及数据空间；业务规则和 CSV 读写放在 core 中。
三大业务板块独立，基础档案维护放在辅助导航组。此包仅用于线上比赛演示。
"""
from functools import partial
import logging
import tempfile
import uuid
from pathlib import Path
import streamlit as st
from filelock import Timeout
from config import ROOT
from core.storage import StorageError
from core.session_store import SessionCsvStore
from core.demo import seed_demo, reset_demo_orders
from views import planner, groups, importer, orders

st.set_page_config(page_title="校园智汇 · 我的校园生活计划", page_icon="📚", layout="wide", initial_sidebar_state="expanded")
st.markdown("<style>" + (ROOT / "assets/style.css").read_text(encoding="utf-8-sig") + "</style>", unsafe_allow_html=True)
st.markdown('<div class="brand-banner">校园智汇 | 我的校园生活计划</div>', unsafe_allow_html=True)
with st.sidebar:
    st.markdown("# 📚 校园智汇")
    st.caption("大学生活 · 课程协同与任务管理")
    # 线上包固定为演示模式，不提供进入真实业务空间的入口。
    demo = True
    st.caption("作业 · 备考 · 社团 · 比赛")
    st.divider()
try:
    # 每个浏览器会话使用独立演示目录，避免评委互相修改同一份样例。
    if "demo_session" not in st.session_state:
        st.session_state.demo_session = uuid.uuid4().hex
    demo_root = Path(tempfile.gettempdir()) / "campus_life_v2_sessions" / st.session_state.demo_session
    with st.spinner("加载中..."):
        store = SessionCsvStore(demo_root)
        if demo:
            seed_demo(store)
    with st.sidebar:
        # 仅覆盖当前浏览器会话的演示计划，不影响其他访客。
        st.caption("重新加载会替换当前演示计划和历史记录")
        if st.button("一键加载演示数据", key="load_demo", use_container_width=True):
            reset_demo_orders(store)
            st.success("已重新加载 5 条校园计划。")
except (StorageError, OSError, Timeout) as exc:
    st.error(f"无法打开数据目录：{exc}")
    st.stop()

# Streamlit 原生多页导航：每个页面一个 render 函数，便于单独修改和测试。
pages = {
    "我的校园生活": [
        st.Page(partial(planner.render, store), title="我的一天", icon="☀️", url_path="today", default=True),
        st.Page(partial(planner.create, store), title="记一件事", icon="✍️", url_path="new"),
        st.Page(partial(groups.render, store), title="课程与活动", icon="📚", url_path="groups"),
        st.Page(partial(importer.render, store), title="截图转计划", icon="📷", url_path="import"),
    ],
    "整理计划": [
        st.Page(partial(orders.render, store), title="调整任务状态", icon="📝", url_path="manage"),
    ],
}
page = st.navigation(pages)
with st.sidebar:
    st.divider()
    st.caption("校园计划：截止前 3 天开始准备")
    st.markdown('<div class="core-formula">给自己留一点余量：截止前 3 天提醒开始。</div>', unsafe_allow_html=True)
try:
    page.run()
except (StorageError, OSError, Timeout) as exc:
    logging.exception("数据操作失败")
    st.error(f"数据暂时不可用：{exc}。已有快照不会被覆盖，请检查磁盘和文件占用后重试。")

