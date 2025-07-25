import os
import streamlit
import logging
from sys import stdout

# Настройка логгирования (для отладки)
logging.basicConfig(level=logging.DEBUG, stream=stdout)
log = logging.getLogger(__name__)

# Путь к head.html (если он в той же папке, оставьте как есть)
head_content_path = os.path.join(os.path.dirname(__file__), "head.html")

def _customize_index_html():
    # 1. Находим стандартный index.html Streamlit
    streamlit_package_dir = os.path.dirname(streamlit.__file__)
    index_path = os.path.join(streamlit_package_dir, "static", "index.html")
    log.debug(f"Путь к index.html: {index_path}")

    # 2. Читаем оригинальный index.html
    with open(index_path, "r") as f:
        index_html = f.read()

    # 3. Читаем ваш head.html
    with open(head_content_path, "r") as f:
        head_content = f.read()

    # 4. Вставляем содержимое head.html перед </head>
    index_html = index_html.replace("</head>", f"{head_content}</head>")

    # 5. (Опционально) Меняем заголовок страницы
    index_html = index_html.replace(
        "<title>Streamlit</title>", 
        "<title>Моё приложение</title>"
    )

    # 6. Перезаписываем index.html
    with open(index_path, "w") as f:
        f.write(index_html)

# Вызываем функцию
_customize_index_html()
