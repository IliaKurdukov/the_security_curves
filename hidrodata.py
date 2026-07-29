"""
Заглушка для старого URL Streamlit Cloud.
Главное приложение: app.py → https://exceedance-curves.streamlit.app/

В analytics.csv пишем только клик по кнопке перехода на новый адрес
(не простой заход на страницу и не авторедирект).
"""

import streamlit as st
import streamlit.components.v1 as components

from analytics import log_stub_visit

NEW_URL = "https://exceedance-curves.streamlit.app/"

st.set_page_config(
    page_title="Exceedance curves — moved",
    page_icon="📉",
    layout="centered",
)

st.title("📉 Exceedance curves")
st.subheader("Приложение переехало / The app has moved")

st.markdown(
    """
Мы сменили адрес. Нажмите кнопку ниже, чтобы открыть актуальную версию.

---

This app has moved. Click the button below to open the current version.
"""
)

if st.button(
    "Открыть новое приложение / Open new app",
    type="primary",
    use_container_width=True,
):
    # Считаем только осознанный переход по кнопке
    log_stub_visit()
    st.session_state["_stub_redirect"] = True

if st.session_state.get("_stub_redirect"):
    st.info("Переход… / Redirecting…")
    components.html(
        f"""
        <script>
        window.top.location.href = "{NEW_URL}";
        </script>
        """,
        height=0,
    )
