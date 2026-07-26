"""
Заглушка для старого URL Streamlit Cloud.
Главное приложение: app.py → https://exceedance-curves.streamlit.app/
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

# Учёт захода по старой ссылке (тот же analytics.csv, маркер __old_url_stub__)
log_stub_visit()

st.title("📉 Exceedance curves")
st.subheader("Приложение переехало / The app has moved")

st.markdown(
    f"""
Мы сменили адрес. Откройте актуальную версию здесь:

**[{NEW_URL}]({NEW_URL})**

---

This app has moved to a new address:

**[{NEW_URL}]({NEW_URL})**
"""
)

st.link_button("Открыть новое приложение / Open new app", NEW_URL, type="primary")

st.caption("Через несколько секунд страница попытается перейти автоматически.")

# Клиентский редирект (не HTTP 301, но удобно для закладок)
components.html(
    f"""
    <script>
    setTimeout(function () {{
      window.top.location.href = "{NEW_URL}";
    }}, 4000);
    </script>
    <p style="font-family: sans-serif; color: #666; font-size: 0.9rem;">
      Redirecting in 4 seconds…
    </p>
    """,
    height=40,
)
