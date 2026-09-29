import pandas as pd
import streamlit as st
from core.recognition import recognize_local, file_hash, validation_errors, FIELDS
from core.service import add_campus_task
from views.common import header
from core.rules import parse_date
LABELS={"customer_name":"课程 / 活动","product_name":"待办事项","product_code":"编号（可选）","quantity":"数量","unit":"单位","delivery_deadline":"截止日期"}
def render(store):
    header("CAPTURE / OCR","截图转计划","上传课程通知、作业要求或活动安排截图，识别后核对并生成待办。"); st.markdown('<div class="flow">01 上传截图 → 02 识别文字 → 03 核对日期 → 04 加入我的计划</div>',unsafe_allow_html=True)
    st.caption("只有星期、节次而没有具体日期的课表不会自动生成任务，避免把循环课表误当成一次性截止日期。")
    uploaded=st.file_uploader("上传课程、作业或活动截图",type=["png","jpg","jpeg","webp","pdf"],help="单文件不超过 20MB，PDF 最多 12 页。")
    if uploaded is None: st.info("上传一张清晰截图即可开始。"); return
    raw=uploaded.getvalue(); digest=file_hash(raw); key="campus-ocr:"+str(store.root)+":"+digest
    if st.button("开始识别",type="primary",use_container_width=True):
        try: st.session_state[key]=recognize_local(raw,uploaded.name)
        except (ValueError,RuntimeError,OSError) as exc: st.error(str(exc))
    result=st.session_state.get(key)
    if not result:return
    if result["issues"]: st.warning("识别结果需要核对："+"；".join(result["issues"]))
    with st.expander("查看识别原文"): st.text(result["raw_text"] or "未提取到文字。")
    frame=pd.DataFrame([{k:r.get(k,"") for k in FIELDS} for r in result["rows"]])
    edited=st.data_editor(frame,column_config={k:st.column_config.TextColumn(v) for k,v in LABELS.items()},hide_index=True,num_rows="dynamic",use_container_width=True,key="editor:"+key)
    confirmed=st.checkbox("我已核对课程 / 活动、待办事项和具体截止日期",key="confirm:"+key)
    if st.button("加入我的计划",disabled=not confirmed,type="primary"):
        try:
            rows=edited.fillna("").to_dict("records"); errors=validation_errors(rows)
            if errors: raise ValueError("；".join(errors))
            for row in rows:
                add_campus_task(store,row.get("product_name"),row.get("customer_name"),parse_date(row.get("delivery_deadline")),"OCR 截图生成的计划")
            st.success(f"已加入 {len(rows)} 件计划。")
        except (ValueError,OSError) as exc: st.error(str(exc))
