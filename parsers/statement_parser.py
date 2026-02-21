import pandas as pd
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

class StatementParser:
    def __init__(self):
        self.transaction_patterns = [
            r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(-?\$?\d{1,3}(?:,\d{3})*\.\d{2})',
            r'(\d{1,2}/\d{1,2}/\d{2,4})\s+(.+?)\s+(\$?\d+\.\d{2})',
            r'(\d{4}-\d{2}-\d{2})\s+(.+?)\s+(-?\$?\d+\.\d{2})'
        ]
        self.date_columns = [
            "date", "transaction date", "posting date", "posted date",
            "trans date", "transaction_date", "posting_date", "post date"
        ]
        self.description_columns = [
            "description", "details", "merchant", "payee", "name",
            "memo", "transaction", "transaction description"
        ]
        self.amount_columns = ["amount", "amt", "value"]
        self.debit_columns = ["debit", "withdrawal", "charge", "outflow"]
        self.credit_columns = ["credit", "deposit", "payment", "inflow"]
        self.type_columns = ["type", "transaction type", "trans type", "debit/credit"]
        self.credit_keywords = [
            "payment", "credit", "refund", "reversal", "chargeback",
            "return", "adjustment"
        ]
    
    def parse_statement(self, filepath: str, mapping: Optional[Dict[str, str]] = None, statement_type: str = "bank") -> List[Dict[str, Any]]:
        path_lower = filepath.lower()
        if path_lower.endswith(('.csv', '.xlsx', '.xls')):
            return self._parse_spreadsheet(filepath, mapping=mapping, statement_type=statement_type)
        else:
            raise ValueError("Unsupported file format (CSV/Excel only)")

    def preview_spreadsheet(self, filepath: str, max_rows: int = 5) -> Dict[str, Any]:
        df = self._read_spreadsheet(filepath)
        df = df.fillna("")
        columns = df.columns.tolist()
        sample_rows = df.head(max_rows).to_dict(orient="records")
        mapping = self._map_columns(columns)
        return {
            "columns": columns,
            "sample_rows": sample_rows,
            "suggested_mapping": mapping
        }
    
    def _read_spreadsheet(self, filepath: str) -> pd.DataFrame:
        path_lower = filepath.lower()
        if path_lower.endswith('.csv'):
            return pd.read_csv(filepath, dtype=str, sep=None, engine="python", on_bad_lines="skip")
        return pd.read_excel(filepath, dtype=str)

    def _parse_spreadsheet(self, filepath: str, mapping: Optional[Dict[str, str]] = None, statement_type: str = "bank") -> List[Dict[str, Any]]:
        df = self._read_spreadsheet(filepath)
        
        df = df.fillna("")
        if mapping:
            normalized = {k: (v if v else None) for k, v in mapping.items()}
            # If mapping doesn't match this file's columns, fall back to auto-map
            if any(v and v not in df.columns for v in normalized.values()):
                col_map = self._map_columns(df.columns.tolist())
            else:
                col_map = normalized
        else:
            col_map = self._map_columns(df.columns.tolist())
        transactions = []

        for _, row in df.iterrows():
            try:
                date_str = self._get_row_value(row, col_map.get("date"))
                description = self._get_row_value(row, col_map.get("description"))
                amount_str = self._get_row_value(row, col_map.get("amount"))
                debit_str = self._get_row_value(row, col_map.get("debit"))
                credit_str = self._get_row_value(row, col_map.get("credit"))
                type_str = self._get_row_value(row, col_map.get("type"))

                if not date_str:
                    continue

                date = self._parse_date(str(date_str))
                description = str(description).strip() if description else ""

                amount = None
                is_credit = False

                # Prefer explicit debit/credit columns if present
                if debit_str:
                    debit = self._parse_amount(str(debit_str))
                    if debit != 0.0:
                        amount = -abs(debit)
                if amount is None and credit_str:
                    credit = self._parse_amount(str(credit_str))
                    if credit != 0.0:
                        amount = abs(credit)
                        is_credit = True

                # If type column exists, use it to determine sign/credit flag
                if amount is None and type_str:
                    type_lower = str(type_str).lower()
                    if "credit" in type_lower or "deposit" in type_lower:
                        is_credit = True
                    elif "debit" in type_lower or "withdrawal" in type_lower:
                        is_credit = False

                if amount_str:
                    amount = self._parse_amount(str(amount_str))
                else:
                    debit = self._parse_amount(str(debit_str)) if debit_str else 0.0
                    credit = self._parse_amount(str(credit_str)) if credit_str else 0.0
                    if debit != 0.0 or credit != 0.0:
                        amount = credit - debit
                        if credit != 0.0 and debit == 0.0:
                            is_credit = True

                if amount is None:
                    continue

                # Exclude credits: positive amounts or credit flag
                if is_credit or amount > 0:
                    continue

                transactions.append({
                    'date': date,
                    'description': description or "Unknown",
                    'amount': amount,
                    'category': None
                })
            except (ValueError, IndexError):
                continue

        return self._clean_transactions(transactions, statement_type=statement_type)
    
    def _parse_date(self, date_str: str) -> str:
        formats = ['%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y']

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        raise ValueError(f"Unable to parse date: {date_str}")
    
    def _parse_amount(self, amount_str: str) -> float:
        amount_str = amount_str.strip()
        if amount_str == "":
            raise ValueError("Empty amount")

        negative = False
        if amount_str.startswith("(") and amount_str.endswith(")"):
            negative = True
            amount_str = amount_str[1:-1]

        amount_str = amount_str.replace('$', '').replace(',', '').replace(' ', '')

        if amount_str.upper().endswith("DR"):
            negative = True
            amount_str = amount_str[:-2]
        elif amount_str.upper().endswith("CR"):
            amount_str = amount_str[:-2]
        
        if amount_str.startswith('-'):
            return -float(amount_str[1:])
        value = float(amount_str)
        return -value if negative else value
    
    def _clean_transactions(self, transactions: List[Dict[str, Any]], statement_type: str = "bank") -> List[Dict[str, Any]]:
        transactions = self._normalize_signs(transactions, statement_type=statement_type)
        cleaned = []
        seen = set()
        
        for transaction in transactions:
            if not transaction.get('description'):
                continue
            key = (transaction['date'], transaction['description'], transaction['amount'])
            if key not in seen and abs(transaction['amount']) > 0.01:
                cleaned.append(transaction)
                seen.add(key)
        
        return sorted(cleaned, key=lambda x: x['date'])

    def _normalize_signs(self, transactions: List[Dict[str, Any]], statement_type: str = "bank") -> List[Dict[str, Any]]:
        if not transactions:
            return transactions

        if statement_type == "credit":
            for t in transactions:
                description = (t.get('description') or "").lower()
                if any(k in description for k in self.credit_keywords):
                    t['amount'] = abs(t.get('amount', 0))
                else:
                    t['amount'] = -abs(t.get('amount', 0))
            return transactions

        has_negative = any(t.get('amount', 0) < 0 for t in transactions)
        if has_negative:
            return transactions

        # Heuristic: if no negatives exist, assume this is a credit card statement
        # and treat most amounts as expenses (negative), except payments/refunds.
        for t in transactions:
            description = (t.get('description') or "").lower()
            if any(k in description for k in self.credit_keywords):
                t['amount'] = abs(t.get('amount', 0))
            else:
                t['amount'] = -abs(t.get('amount', 0))

        return transactions

    def _normalize_header(self, header: str) -> str:
        return re.sub(r'[\s_-]+', ' ', str(header).strip().lower())

    def _map_columns(self, columns: List[str]) -> Dict[str, str]:
        normalized = {self._normalize_header(c): c for c in columns}

        def find_match(candidates):
            for cand in candidates:
                if cand in normalized:
                    return normalized[cand]
            for key, orig in normalized.items():
                for cand in candidates:
                    if cand in key:
                        return orig
            return None

        return {
            "date": find_match(self.date_columns),
            "description": find_match(self.description_columns),
            "amount": find_match(self.amount_columns),
            "debit": find_match(self.debit_columns),
            "credit": find_match(self.credit_columns),
            "type": find_match(self.type_columns),
        }

    def _get_row_value(self, row: pd.Series, column_name: str) -> Any:
        if not column_name:
            return ""
        return row.get(column_name, "")
