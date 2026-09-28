"""具体任务资料库：图片、介绍、规格、任务步骤清单、完成检查表集中维护。"""
import streamlit as st
from core.service import save_product, save_image
from views.common import header, product_details, notify, saved


def render(store):
    header("TASK LIBRARY", "具体任务资料库", "从一个具体任务，查到完整资料、任务步骤清单与配套检查要求。")
    notify()
    products = store.read()["products"]
    query = st.text_input("搜索具体任务", placeholder="具体任务名称 / 具体任务编码")
    filtered = [p for p in products if query.casefold() in (p["name"] + p["code"]).casefold()]
    if not filtered:
        st.info("暂无匹配具体任务，可在下方新增资料。")
    for product in filtered:
        with st.expander(f"📚 {product['name']}　|　{product['code']}　|　{product['unit']}"):
            product_details(product, store)
    st.divider()
    mode = st.radio("资料操作", ["新增具体任务", "修改具体任务资料"], horizontal=True)
    row = {}
    if mode == "修改具体任务资料":
        if not products:
            st.info("暂无可修改具体任务。")
            return
        row = st.selectbox("选择具体任务资料", products, format_func=lambda p: f"{p['code']} · {p['name']}")
    with st.form("product_form"):
        a, b, c = st.columns([2, 2, 1])
        values = {}
        values["name"] = a.text_input("具体任务名称 *", row.get("name", ""), max_chars=100)
        values["code"] = b.text_input("具体任务编码 *", row.get("code", ""), max_chars=100)
        values["unit"] = c.text_input("计量单位 *", row.get("unit", "项"), max_chars=15)
        image = st.file_uploader("上传具体任务图片（可选）", type=["png", "jpg", "jpeg", "webp"])
        values["description"] = st.text_area("具体任务介绍", row.get("description", ""), max_chars=6000)
        a, b = st.columns(2)
        values["specs"] = a.text_area("任务要求", row.get("specs", ""), placeholder="例如：提交 PDF；不少于 1500 字；小组共同完成", height=130, max_chars=6000)
        values["checklist"] = b.text_area("完成检查表（每行一项）", row.get("checklist", ""), placeholder="内容已核对\n小组成员已确认\n已提交到课程平台", height=130, max_chars=6000)
        values["bom"] = st.text_area("任务步骤与资源清单", row.get("bom", ""), placeholder="每行一项：步骤 | 所需资源 | 完成标准\n01 | 课程教材与笔记 | 完成指定习题", max_chars=12000)
        submit = st.form_submit_button("保存具体任务资料", type="primary")
    if submit:
        try:
            values["image_path"] = save_image(store, image.getvalue()) if image else row.get("image_path", "")
            save_product(store, values, row.get("id"))
            saved("具体任务全套资料已保存。")
        except ValueError as exc:
            st.error(str(exc))
