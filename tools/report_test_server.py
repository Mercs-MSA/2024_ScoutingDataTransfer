from flask import Flask, render_template

app = Flask(__name__, template_folder='../templates')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<template_name>')
def render_template_by_name(template_name):
    try:
        return render_template(f'{template_name}.html', team=9999, event="devtest")
    except Exception:
        return f"Template {template_name}.html not found", 404


if __name__ == '__main__':
    app.run(debug=True)