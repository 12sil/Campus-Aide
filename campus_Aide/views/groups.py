"""课程与活动按归属显示计划，保留双向查看。"""
import streamlit as st
from core.query import enriched_orders
from core.service import save_customer
from views.common import header, notify, saved
from views.planner import task_card

def render(store):
    header('COURSES / CLUBS / EXAMS', '课程与活动', '从一门课看待办，也可以从一件事找到它所属的课程或活动。')
    notify()
    data = store.read()
    tasks = enriched_orders(data)
    mode = st.radio('查找方式', ['按课程 / 活动', '按任务查归属'], horizontal=True)
    if mode == '按任务查归属':
        keyword = st.text_input('任务关键词', placeholder='高数、听力、海报……')
        selected = [t for t in tasks if keyword.casefold() in t['current_product'].casefold()]
    else:
        groups = data['customers']
        if not groups:
            st.info('先去“记一件事”建立第一门课或活动。')
            return
        group = st.selectbox('课程 / 考试 / 社团 / 竞赛', groups, format_func=lambda g:g['name'])
        selected = [t for t in tasks if t['customer_id'] == group['id']]
        done = sum(t['status']=='已完成' for t in selected)
        total = sum(t['status']!='已取消' for t in selected)
        st.progress(done / total if total else 0, text=f'已完成 {done} / {total} 件事')
        with st.expander('老师、伙伴与地点'):
            with st.form('group_info'):
                contact = st.text_input('老师 / 联系伙伴', group['contact'])
                address = st.text_input('教室 / 活动地点', group['address'])
                notes = st.text_area('课程或活动说明', group['notes'])
                submit = st.form_submit_button('保存信息')
            if submit:
                try:
                    save_customer(store, {**group, 'contact':contact, 'address':address, 'notes':notes}, group['id'])
                    saved('课程活动信息已更新。')
                except ValueError as exc:
                    st.error(str(exc))
    if not selected:
        st.info('暂无匹配的计划。')
    for task in sorted(selected, key=lambda t:t['delivery_deadline']):
        task_card(store, task)
