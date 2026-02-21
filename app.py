from flask import Flask, render_template, request, jsonify, send_from_directory, abort
import os
from werkzeug.utils import secure_filename
from parsers.statement_parser import StatementParser
from analysis.expense_analyzer import ExpenseAnalyzer
from db import init_db, migrate_json_if_present, list_transactions, add_transactions, clear_transactions, delete_transaction, get_conn, list_category_rules, add_category_rule, delete_category_rule
import uuid
import time

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
init_db()
migrate_json_if_present()


def cleanup_old_uploads(days: int = 30) -> int:
    cutoff = time.time() - (days * 24 * 60 * 60)
    removed = 0
    for name in os.listdir(app.config['UPLOAD_FOLDER']):
        path = os.path.join(app.config['UPLOAD_FOLDER'], name)
        if not os.path.isfile(path):
            continue
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
        except OSError:
            pass
    return removed


cleanup_old_uploads()

@app.route('/')
def index():
    return render_template('index.html')

def _save_upload(file) -> str:
    file_id = uuid.uuid4().hex
    filename = secure_filename(file.filename)
    stored_name = f"{file_id}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
    file.save(filepath)
    return filepath


@app.route('/upload/preview', methods=['POST'])
def upload_preview():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    files = request.files.getlist('file')
    files = [f for f in files if f and f.filename]
    if not files:
        return jsonify({'error': 'No file selected'}), 400

    parser = StatementParser()
    file_ids = []
    preview = None
    errors = []

    for idx, file in enumerate(files):
        filepath = _save_upload(file)
        file_ids.append(os.path.basename(filepath))
        if preview is None:
            if filepath.lower().endswith(('.csv', '.xlsx', '.xls')):
                try:
                    preview = parser.preview_spreadsheet(filepath)
                except Exception as e:
                    errors.append(f"{file.filename}: {e}")
            else:
                errors.append(f"{file.filename}: unsupported file format (CSV/Excel only)")

    return jsonify({
        "success": True,
        "file_ids": file_ids,
        "preview": preview,
        "errors": errors
    })


@app.route('/upload/preview-file', methods=['GET'])
def preview_file():
    file_id = request.args.get('file_id')
    if not file_id:
        return jsonify({'error': 'file_id is required'}), 400

    file_id = os.path.basename(file_id)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    if not os.path.exists(filepath):
        return jsonify({'error': 'file not found'}), 404

    parser = StatementParser()
    if filepath.lower().endswith(('.csv', '.xlsx', '.xls')):
        try:
            preview = parser.preview_spreadsheet(filepath)
            return jsonify({'success': True, 'type': 'table', **preview})
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    return jsonify({'error': 'Unsupported file format (CSV/Excel only)'}), 400


@app.route('/upload/view/<path:file_id>', methods=['GET'])
def view_uploaded_file(file_id):
    file_id = os.path.basename(file_id)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    if not os.path.exists(filepath):
        return abort(404)

    parser = StatementParser()
    filename = file_id.split('_', 1)[-1]

    if filepath.lower().endswith(('.csv', '.xlsx', '.xls')):
        df = parser._read_spreadsheet(filepath).fillna("")
        columns = df.columns.tolist()
        rows = df.to_dict(orient="records")
        header_html = "".join([f"<th>{c}</th>" for c in columns])
        body_html = "".join([
            "<tr>" + "".join([f"<td>{(row.get(c) or '')}</td>" for c in columns]) + "</tr>"
            for row in rows
        ])
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{filename}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    .bar {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }}
    .btn {{ background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 8px 12px; text-decoration: none; font-size: 14px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 8px; font-size: 14px; }}
    th {{ background: #f3f4f6; text-align: left; }}
    tr:nth-child(even) td {{ background: #fafafa; }}
  </style>
</head>
<body>
  <div class="bar">
    <h2 style="margin: 0;">{filename}</h2>
    <a class="btn" href="/upload/file/{file_id}" download>Download</a>
  </div>
  <table>
    <thead><tr>{header_html}</tr></thead>
    <tbody>{body_html}</tbody>
  </table>
</body>
</html>
"""

    return abort(400)


@app.route('/upload/commit', methods=['POST'])
def upload_commit():
    data = request.json or {}
    file_ids = data.get('file_ids', [])
    mapping = data.get('mapping') or {}
    statement_type = data.get('statement_type') or "bank"
    bank_name = data.get('bank_name') or None

    if not file_ids:
        return jsonify({'error': 'No uploaded files to import'}), 400

    parser = StatementParser()
    all_transactions = []
    errors = []

    for file_id in file_ids:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        if not os.path.exists(filepath):
            errors.append(f"{file_id}: file not found")
            continue
        try:
            parsed = parser.parse_statement(filepath, mapping=mapping, statement_type=statement_type)
            if not parsed:
                errors.append(f"{file_id}: no transactions detected")
            else:
                all_transactions.extend(parsed)
        except Exception as e:
            errors.append(f"{file_id}: {e}")

    if not all_transactions and errors:
        return jsonify({'error': " | ".join(errors)}), 400

    _, added, skipped = add_transactions(all_transactions, source="upload", bank=bank_name)
    transactions = list_transactions()
    analyzer = ExpenseAnalyzer(custom_categories=list_category_rules())
    analysis = analyzer.analyze_expenses(transactions)

    return jsonify({
        'success': True,
        'transactions': transactions,
        'analysis': analysis,
        'imported': len(all_transactions),
        'added': added,
        'skipped': skipped,
        'errors': errors
    })


@app.route('/upload/cleanup', methods=['POST'])
def upload_cleanup():
    data = request.json or {}
    file_ids = data.get('file_ids', [])
    removed = 0
    for file_id in file_ids:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                removed += 1
            except OSError:
                pass
    return jsonify({'success': True, 'removed': removed})


@app.route('/upload/cleanup-all', methods=['POST'])
def upload_cleanup_all():
    removed = 0
    for name in os.listdir(app.config['UPLOAD_FOLDER']):
        path = os.path.join(app.config['UPLOAD_FOLDER'], name)
        if os.path.isfile(path):
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    return jsonify({'success': True, 'removed': removed})


@app.route('/upload/list', methods=['GET'])
def list_uploads():
    cleanup_old_uploads()
    files = []
    for name in os.listdir(app.config['UPLOAD_FOLDER']):
        path = os.path.join(app.config['UPLOAD_FOLDER'], name)
        if not os.path.isfile(path):
            continue
        original = name.split('_', 1)[-1]
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0
        files.append({
            "file_id": name,
            "name": original,
            "mtime": mtime
        })
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return jsonify({"files": files})


@app.route('/upload/file/<path:file_id>', methods=['GET'])
def get_uploaded_file(file_id):
    file_id = os.path.basename(file_id)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    if not os.path.exists(filepath):
        return abort(404)
    return send_from_directory(app.config['UPLOAD_FOLDER'], file_id, as_attachment=False)

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    transactions = data.get('transactions', [])
    
    analyzer = ExpenseAnalyzer(custom_categories=list_category_rules())
    analysis = analyzer.analyze_expenses(transactions)
    
    return jsonify(analysis)

@app.route('/transactions', methods=['GET'])
def get_transactions():
    transactions = list_transactions()
    analyzer = ExpenseAnalyzer(custom_categories=list_category_rules())
    analysis = analyzer.analyze_expenses(transactions)
    return jsonify({'transactions': transactions, 'analysis': analysis})

@app.route('/transactions', methods=['POST'])
def add_transaction():
    data = request.json or {}
    date = data.get('date')
    description = data.get('description', '').strip()
    amount = data.get('amount')
    category = data.get('category')
    bank_name = data.get('bank_name') or None

    if not date or not description or amount is None:
        return jsonify({'error': 'date, description, and amount are required'}), 400

    try:
        amount = float(amount)
    except ValueError:
        return jsonify({'error': 'amount must be a number'}), 400

    transaction = {
        'date': date,
        'description': description,
        'amount': amount,
        'category': category
    }

    add_transactions([transaction], source="manual", bank=bank_name)
    transactions = list_transactions()
    analyzer = ExpenseAnalyzer(custom_categories=list_category_rules())
    analysis = analyzer.analyze_expenses(transactions)
    return jsonify({'success': True, 'transactions': transactions, 'analysis': analysis})


@app.route('/transactions/<int:txn_id>', methods=['DELETE'])
def remove_transaction(txn_id: int):
    removed = delete_transaction(txn_id)
    transactions = list_transactions()
    analyzer = ExpenseAnalyzer(custom_categories=list_category_rules())
    analysis = analyzer.analyze_expenses(transactions)
    return jsonify({'success': removed, 'transactions': transactions, 'analysis': analysis})


@app.route('/transactions/<int:txn_id>', methods=['PATCH'])
def update_transaction(txn_id: int):
    data = request.json or {}
    category = data.get('category')
    description = data.get('description')
    amount = data.get('amount')
    date = data.get('date')

    fields = []
    values = []
    if category is not None:
        fields.append("category = ?")
        values.append(category if category != "" else None)
    if description is not None:
        fields.append("description = ?")
        values.append(description.strip())
    if amount is not None:
        try:
            amount = float(amount)
            fields.append("amount = ?")
            values.append(amount)
        except ValueError:
            return jsonify({'error': 'amount must be a number'}), 400
    if date is not None:
        fields.append("date = ?")
        values.append(date)

    if not fields:
        return jsonify({'error': 'No fields to update'}), 400

    values.append(txn_id)
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE transactions SET {', '.join(fields)} WHERE id = ?",
            values
        )
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'Transaction not found'}), 404

    transactions = list_transactions()
    analyzer = ExpenseAnalyzer()
    analysis = analyzer.analyze_expenses(transactions)
    return jsonify({'success': True, 'transactions': transactions, 'analysis': analysis})


@app.route('/categories', methods=['GET'])
def get_categories():
    return jsonify({'categories': list_category_rules()})


@app.route('/categories', methods=['POST'])
def create_category():
    data = request.json or {}
    name = (data.get('name') or '').strip()
    keywords = data.get('keywords') or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(',')]
    if not name or not keywords:
        return jsonify({'error': 'name and keywords are required'}), 400
    try:
        rule = add_category_rule(name, keywords)
    except Exception:
        return jsonify({'error': 'category already exists'}), 400
    return jsonify({'success': True, 'category': rule, 'categories': list_category_rules()})


@app.route('/categories/<int:rule_id>', methods=['DELETE'])
def remove_category(rule_id: int):
    deleted = delete_category_rule(rule_id)
    return jsonify({'success': deleted, 'categories': list_category_rules()})

@app.route('/transactions/clear', methods=['POST'])
def clear_all_transactions():
    clear_transactions()
    # Also clear any uploaded files on full reset
    for name in os.listdir(app.config['UPLOAD_FOLDER']):
        path = os.path.join(app.config['UPLOAD_FOLDER'], name)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
