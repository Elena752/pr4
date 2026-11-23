import ast
import os
import sqlite3
from operator import add, sub, mul, truediv, floordiv, mod, pow, neg, pos

from flask import Flask, render_template_string, request

app = Flask(__name__)

DB_PATH = os.environ.get("DB_PATH", "/app/data/calc.db")

OPS = {
    ast.Add: add,
    ast.Sub: sub,
    ast.Mult: mul,
    ast.Div: truediv,
    ast.FloorDiv: floordiv,
    ast.Mod: mod,
    ast.Pow: pow,
    ast.USub: neg,
    ast.UAdd: pos,
}


def evaluate(expr):
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            return OPS[type(node.op)](_eval(node.operand))
        raise ValueError("Недопустимое выражение")

    return _eval(ast.parse(expr, mode="eval").body)


def format_result(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = get_db()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS history ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "expression TEXT NOT NULL, "
        "result TEXT NOT NULL, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()
    conn.close()


def save_history(expression, result):
    conn = get_db()
    conn.execute(
        "INSERT INTO history (expression, result) VALUES (?, ?)",
        (expression, result),
    )
    conn.commit()
    conn.close()


def load_history():
    conn = get_db()
    rows = conn.execute(
        "SELECT expression, result, created_at FROM history ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return rows


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None
    expression = ""
    if request.method == "POST":
        expression = request.form.get("expression", "").strip()
        if expression:
            try:
                result = format_result(evaluate(expression))
                save_history(expression, result)
                expression = ""
            except ZeroDivisionError:
                error = "Деление на ноль"
            except (ValueError, SyntaxError, OverflowError, RecursionError):
                error = "Некорректное выражение"
    return render_template_string(
        TEMPLATE, result=result, error=error, expression=expression,
        history=load_history(),
    )


@app.route("/clear", methods=["POST"])
def clear():
    conn = get_db()
    conn.execute("DELETE FROM history")
    conn.commit()
    conn.close()
    return render_template_string(
        TEMPLATE, result=None, error=None, expression="", history=load_history(),
    )


TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Веб-калькулятор</title>
<style>
  body { font-family: Arial, sans-serif; background: #f0f2f5; margin: 0; padding: 40px 16px; }
  .card { max-width: 460px; margin: 0 auto; background: #fff; border-radius: 10px;
          padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.12); }
  h1 { font-size: 22px; margin-top: 0; }
  h2 { font-size: 16px; margin-bottom: 8px; }
  input[name=expression] { width: 100%; box-sizing: border-box; padding: 10px;
                            font-size: 18px; border: 1px solid #ccc; border-radius: 6px; }
  button { padding: 10px 20px; font-size: 15px; margin-top: 10px; border: none;
           border-radius: 6px; background: #2563eb; color: #fff; cursor: pointer; }
  button.gray { background: #9ca3af; }
  .result { font-size: 24px; margin: 16px 0 0; }
  .error { color: #c0392b; margin: 12px 0 0; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 14px; }
  td, th { padding: 6px 4px; border-bottom: 1px solid #eee; text-align: left; }
  .empty { color: #6b7280; font-size: 14px; }
</style>
</head>
<body>
<div class="card">
  <h1>Веб-калькулятор</h1>
  <form method="post" action="/">
    <input name="expression" placeholder="Например: 2 + 2 * 10" value="{{ expression }}" autofocus>
    <button type="submit">Посчитать</button>
  </form>
  {% if result is not none %}<p class="result">= {{ result }}</p>{% endif %}
  {% if error %}<p class="error">{{ error }}</p>{% endif %}

  <h2>История вычислений</h2>
  {% if history %}
  <table>
    <tr><th>Выражение</th><th>Результат</th><th>Время (UTC)</th></tr>
    {% for row in history %}
    <tr><td>{{ row.expression }}</td><td>{{ row.result }}</td><td>{{ row.created_at }}</td></tr>
    {% endfor %}
  </table>
  <form method="post" action="/clear">
    <button class="gray">Очистить историю</button>
  </form>
  {% else %}
  <p class="empty">Пока пусто — введите выражение выше.</p>
  {% endif %}
</div>
</body>
</html>
"""

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
