"""以每日待办、周计划和完成反馈组织校园生活。"""
from datetime import timedelta
import streamlit as st
from core.query import enriched_orders
from core.rules import today_china, parse_date
from core.service import update_status, add_campus_task
from views.common import header, saved, notify

def task_card(store, task):
    with st.container(border=True):
        st.subheader(task['current_product'])
        st.caption(f"{task['current_customer']} · 截止 {task['delivery_deadline']}")
        remaining = (parse_date(task['delivery_deadline']) - today_china()).days
        state = {'未启动': '待开始', '已启动': '进行中', '已完成': '已完成', '已取消': '已取消'}[task['status']]
        st.write(f"{state} · " + (f"已过截止日 {-remaining} 天" if remaining < 0 else f"距截止 {remaining} 天"))
        if task['status'] == '未启动':
            st.caption(task['label'])
        if task['notes']:
            st.write(task['notes'])
        if task['status'] not in ('已完成', '已取消'):
            a, b = st.columns(2)
            start = a.button('开始做', key='start_'+task['id'], disabled=task['status'] != '未启动')
            done = b.button('完成打卡', key='done_'+task['id'], type='primary')
            if start or done:
                try:
                    update_status(store, task['id'], '已完成' if done else '已启动',
                                  note='校园计划完成打卡' if done else '开始学习', expected_status=task['status'])
                    saved('又完成一件事，做得好！' if done else '已加入进行中。')
                except ValueError as exc:
                    st.error(str(exc))

def render(store):
    today = today_china()
    header('MY CAMPUS / TODAY', '今天，安排得刚刚好', '把作业、备考、社团和比赛放在一起，一件一件完成。')
    notify()
    tasks = enriched_orders(store.read())
    active = [t for t in tasks if t['status'] not in ('已完成', '已取消')]
    end = today + timedelta(days=6-today.weekday())
    focus = [t for t in active if parse_date(t['ship_date']) <= today or t['status']=='已启动']
    a,b,c = st.columns(3)
    a.metric('今天值得关注', len(focus))
    b.metric('本周待交 / 待完成', sum(today <= parse_date(t['delivery_deadline']) <= end for t in active))
    c.metric('已经完成', sum(t['status']=='已完成' for t in tasks))
    st.caption(f"{today:%Y年%m月%d日} · 已开始的任务仍会提醒截止时间；未开始的任务提前 3 天提醒。")
    choice = st.radio('我的视图', ['今天做什么', '本周安排', '全部计划', '完成记录'], horizontal=True)
    if choice == '今天做什么':
        selected = focus
    elif choice == '本周安排':
        selected = [t for t in active if today <= parse_date(t['delivery_deadline']) <= end]
        st.caption('按截止日期列出今天至本周日的安排。更早已逾期的任务见“今天做什么”。')
    elif choice == '完成记录':
        selected = [t for t in tasks if t['status']=='已完成']
    else:
        selected = active
    selected = sorted(selected, key=lambda t:t['delivery_deadline'])
    if not selected:
        st.info('这里暂时没有安排。可以去“记一件事”添加新计划。')
    columns = st.columns(2)
    for i, task in enumerate(selected):
        with columns[i%2]:
            task_card(store, task)

def create(store):
    header('CAPTURE / PLAN', '记一件事', '不用先建任务档案：写下要做的事，选择归属和截止日期即可。')
    notify()
    groups = store.read()['customers']
    with st.form('campus_quick_add', clear_on_submit=True):
        title = st.text_input('要做什么？', placeholder='例如：高数第六章作业、四级听力练习、社团招新海报', max_chars=100)
        options = [g['name'] for g in groups] + ['＋ 新建课程或活动']
        group = st.selectbox('属于哪门课 / 哪个活动？', options)
        new_group = st.text_input('新课程或活动名称（选择新建时填写）', max_chars=100)
        deadline = st.date_input('截止日期', value=today_china()+timedelta(days=3))
        notes = st.text_area('准备做什么 / 和谁一起做？', placeholder='如：小林负责查资料，我负责整理演示稿。', max_chars=2000)
        submitted = st.form_submit_button('加入我的计划', type='primary')
    if submitted:
        try:
            add_campus_task(store, title, new_group if group.startswith('＋') else group, deadline, notes)
            saved('计划已加入，回到“我的一天”就能看到。')
        except ValueError as exc:
            st.error(str(exc))
