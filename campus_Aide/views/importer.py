"""板块三：课程/项目任务分配文件智能导入。独立页面，识别与写入结果明确展示。"""
from config import ROOT
import pandas as pd
import streamlit as st
from core.recognition import recognize_local, file_hash, validation_errors, FIELDS
from core.rules import required_ship_date
from core.service import import_orders
from views.common import header

LABELS = {"customer_name": "课程/项目名称", "product_name": "具体任务名称", "product_code": "具体任务编码（可选）", "quantity": "任务分配数量", "unit": "单位", "delivery_deadline": "任务截止日期"}


def render(store):
    header("03 / SCHEDULE OCR", "课表截图智能识别", "上传课表截图，自动识别课程安排并生成日程。也可识别带任务截止日期的课程/项目安排。")
    st.markdown('<div class="flow">01 上传文件　→　02 智能识别　→　03 规则校验　→　04 自动入单</div>', unsafe_allow_html=True)
    engine = "本地 OCR（免费）"
    st.caption("神经网络 OCR + 字段提取。模糊或缺失字段需要核对，确认后才会写入任务分配。")
    sample = ROOT / "samples" / "课程/项目任务分配样例.png"
    if sample.exists():
        st.download_button("下载任务分配样例图片", sample.read_bytes(), file_name="课程/项目任务分配样例.png", mime="image/png")
    uploaded = st.file_uploader("上传课表截图或课程任务安排", type=["png", "jpg", "jpeg", "webp", "pdf"], help="单文件不超过 20MB，PDF 最多 12 页。")
    if uploaded is None:
        st.info("请上传任务分配文件。完整字段可一键识别入单，无需手动输入。")
        return
    raw = uploaded.getvalue()
    digest = file_hash(raw)
    # 使用文件内容与数据空间共同命名状态，切换演示/正式数据不会复用旧导入状态。
    result_key = "recognition:" + str(store.root) + ":" + digest
    existing = next((x for x in store.read()["imports"] if x["file_hash"] == digest), None)
    if existing:
        st.success(f"该文件已入库，关联任务分配：{existing['order_ids']}。已阻止重复入单。")
        return
    automatic = st.checkbox("识别通过后自动生成任务分配", value=True, help="有缺失、低清晰度或冲突时停止自动保存，保留结果供核对。")
    if st.button("识别并自动入单" if automatic else "开始识别", type="primary", use_container_width=True):
        try:
            with st.spinner("正在识别文字与任务分配字段…"):
                result = recognize_local(raw, uploaded.name)
            st.session_state[result_key] = result
            if automatic and not result["issues"]:
                ids = import_orders(store, result["rows"], digest, uploaded.name, raw, result["engine"], result["raw_text"])
                st.success(f"已自动生成 {len(ids)} 笔任务分配，启动日期已按任务截止日期减 3 天计算。")
                for row in result["rows"]:
                    st.write(f"{row['customer_name']} · {row['product_name']} · {row['quantity']} {row['unit']}　｜　必须启动日 {required_ship_date(row['delivery_deadline'])}")
                st.caption("任务分配已保存，可前往预警看板或双向查询查看。")
                return
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(str(exc))
    result = st.session_state.get(result_key)
    if result:
        st.subheader("识别结果与核对")
        if result["issues"]:
            st.warning("⚠️ 系统拦截：任务分配格式不符合规范，未识别到完整字段。\n\n这是系统的安全校验机制，请上传格式清晰的图片或手动录入。")
            st.caption("规则校验拦截 · 原始文件不会被错误写入任务分配数据。")
        with st.expander("查看识别原文与字段依据"):
            st.text(result["raw_text"] or "未提取到文字。")
            if result["ocr_score"] is not None:
                st.caption(f"最低文字识别分数：{result['ocr_score']:.2f}，仅反映 OCR 字形识别，不代表整张任务分配准确率。")
        frame = pd.DataFrame([{k: row.get(k, "") for k in FIELDS} for row in result["rows"]])
        edited = st.data_editor(frame, column_config={k: st.column_config.TextColumn(v) for k, v in LABELS.items()}, hide_index=True,
                                num_rows="dynamic", use_container_width=True, key="editor:" + result_key)
        confirmed = st.checkbox("已核对课程/项目、具体任务、数量及任务截止日期", key="confirm:" + result_key)
        if st.button("确认结果并入库", disabled=not confirmed, type="primary"):
            try:
                rows = edited.fillna("").to_dict("records")
                errors = validation_errors(rows)
                if errors:
                    raise ValueError("⚠️ 系统拦截：任务分配格式不符合规范，未识别到完整字段。这是系统的安全校验机制，请上传格式清晰的图片或手动录入。")
                ids = import_orders(store, rows, digest, uploaded.name, raw, result["engine"], result["raw_text"])
                st.success(f"已保存 {len(ids)} 笔任务分配；刷新或重复上传不会重复入单。")
            except (ValueError, OSError) as exc:
                st.error(str(exc))
