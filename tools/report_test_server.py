import os
from flask import Flask, render_template, request

from PySide6.QtGui import QPixmap, QGuiApplication
from PySide6.QtCore import QBuffer, QSize
import qtawesome

app = Flask(__name__, template_folder='../templates')

@app.route('/')
def index():
    # render directory of files in templates
    # there is no index file
    template = "<h1>Available templates</h1>"
    for file in os.listdir("templates"):
        if file.endswith(".html"):
            template += f'<a href="/{file.split(".")[0]}?generator=report">{file.split(".")[0]} (report)</a><br>'
            template += f'<a href="/{file.split(".")[0]}?generator=sidebar">{file.split(".")[0]} (sidebar)</a><br>'
    return template

@app.route('/<template_name>')
def render_template_by_name(template_name):
    generator = request.args.get('generator', default="report")

    imbuffer = QBuffer()
    QPixmap("icons/logo16.png").save(imbuffer, "PNG")
    logo_16 = (
        f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
    )

    imbuffer = QBuffer()
    qtawesome.icon("mdi6.close", color="#ffffff").pixmap(
        QSize(30, 30)
    ).save(imbuffer, "PNG")
    close_64 = (
        f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
    )

    imbuffer = QBuffer()
    qtawesome.icon("mdi6.close-thick", color="#f44336").pixmap(
        QSize(30, 30)
    ).save(imbuffer, "PNG")
    x_64 = (
        f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
    )

    try:
        return render_template(f'{template_name}.html', 
                               team=9999, 
                               event="devtest", 
                               timestamp="2025-01-01 00:00:00", 
                               generator=generator, 
                               logo16Base64=logo_16, 
                               closeBase64Icon=close_64,
                                xBase64Icon=x_64,
                               )
    except Exception:
        return f"Template {template_name}.html not found", 404


if __name__ == '__main__':
    qapp = QGuiApplication([])
    app.run(debug=True)