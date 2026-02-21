# Budget Analyzer

A frugal budgeting app that analyzes your bank statements and credit card transactions to help you identify expense-cutting opportunities.
![Arch Dig](<arch.drawio.png>)

```mermaid
flowchart LR
    U[Browser UI<br/>templates/index.html]
    J[Client Logic<br/>static/js/app.js]
    API[Flask API<br/>app.py]
    P[StatementParser<br/>parsers/statement_parser.py]
    A[ExpenseAnalyzer<br/>analysis/expense_analyzer.py]
    DB[(SQLite<br/>data/budget.db)]
    UP[(Uploads Folder<br/>uploads/*.csv)]
    CR[(category_rules table)]

    U -->|fetch JSON| J
    J -->|/upload/preview<br/>/upload/commit<br/>/transactions<br/>/categories| API
    API -->|read files| UP
    API -->|parse rows| P
    API -->|analyze txns| A
    API -->|CRUD txns| DB
    API -->|CRUD categories| CR
    A -->|load txns + rules| DB
    A -->|load custom rules| CR
    API -->|response: transactions,<br/>analysis, added/skipped| J
    J

## Features

- **Multi-format support**: Upload CSV and Excel statements from banks and credit cards
- **Automatic categorization**: Intelligent expense categorization using pattern matching
- **Expense analysis**: Comprehensive analysis with visualizations
- **Smart recommendations**: AI-powered suggestions to reduce expenses
- **Interactive dashboard**: Beautiful, responsive interface with charts and insights
- **Column mapping preview**: Confirm your columns before importing
- **Local storage**: Transactions are stored in SQLite for persistence

## Quick Start

### Python Version
This project currently targets Python 3.12. Using Python 3.14 will fail due to upstream package incompatibilities.

### Pyenv + venv (Recommended on Arch)
```bash
# install build deps once (Arch)
sudo pacman -S --needed base-devel openssl zlib xz tk libffi readline bzip2 sqlite

# install python 3.12 with pyenv
pyenv install 3.12.7
pyenv local 3.12.7

# create and activate venv
python -m venv .venv
source .venv/bin/activate

# install deps
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   python app.py
   ```

3. **Open your browser**:
   Navigate to `http://localhost:5000`

4. **Upload your statements**:
    - Drag and drop or click to upload bank/credit card statements
    - Supports CSV and Excel formats
    - Multiple files can be uploaded at once

5. **Get insights**:
    - View expense breakdown by category
    - See monthly spending trends
    - Receive personalized recommendations to save money
    - Add manual transactions for items that aren't in your statements

## Manual Entries

You can add transactions manually using the form on the homepage. Expenses are stored as negative amounts, income as positive amounts.
All uploaded and manual transactions are stored locally in `data/budget.db`.

## Supported Statement Formats

- **Bank statements**: Checking and savings account statements
- **Credit cards**: All major credit card providers
- **File formats**: PDF, CSV, Excel (.xlsx, .xls)

## Analysis Features

- **Category breakdown**: Food, transport, shopping, entertainment, utilities, healthcare, housing, subscriptions
- **Trend analysis**: Monthly spending patterns over time
- **Top expenses**: Largest transactions identified
- **Subscription analysis**: Recurring charges analysis
- **Cost-cutting recommendations**: Actionable suggestions with potential savings

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: Bootstrap 5, JavaScript
- **Data processing**: Pandas, PDFPlumber
- **Visualization**: Plotly.js
- **File handling**: Multiple format support

## Privacy & Security

- All processing happens locally on your machine
- No data is sent to external servers
- Files are processed in memory and deleted after analysis

## Example Use Cases

1. **Monthly budget review**: Upload monthly statements to see where your money goes
2. **Subscription audit**: Identify recurring charges and cancel unused services
3. **Expense optimization**: Get personalized recommendations to reduce spending
4. **Trend monitoring**: Track spending patterns over multiple months

## Development

The application is modular with separate components:
- `parsers/`: Statement parsing logic
- `analysis/`: Expense analysis and recommendations
- `templates/`: HTML templates
- `static/`: CSS and JavaScript files

## Contributing

Feel free to suggest improvements or report issues to make this budget analyzer more helpful for frugal living!
