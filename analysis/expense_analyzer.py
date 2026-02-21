import pandas as pd
import re
from typing import List, Dict, Any, Tuple
from collections import defaultdict

class ExpenseAnalyzer:
    def __init__(self, custom_categories=None):
        self.categories = {
            'food': ['restaurant', 'food', 'grocery', 'coffee', 'bar', 'dining', 'market', 'bazar', 'bazaar'],
            'transport': ['gas', 'uber', 'lyft', 'taxi', 'subway', 'bus', 'parking', 'toll'],
            'shopping': ['amazon', 'walmart', 'target', 'costco', 'store', 'shop', 'retail'],
            'entertainment': ['netflix', 'spotify', 'movie', 'theater', 'concert', 'gaming'],
            'utilities': ['utility', 'electric', 'gas', 'water', 'internet', 'phone', 'cable', 'wireless', 'mobile', 'cell', 'mint mobile', 'coserv', 'sewer', 'trash'],
            'healthcare': ['pharmacy', 'doctor', 'hospital', 'medical', 'dental'],
            'housing': ['rent', 'mortgage', 'insurance', 'property'],
            'education': ['tuition', 'college', 'university', 'school', '529', 'contribution', 'student loan'],
            'subscriptions': ['subscription', 'membership', 'recurring', 'linkedin', 'adobe', 'icloud'],
            'cash': ['atm', 'cash', 'withdrawal']
        }
        if custom_categories:
            # Custom categories should take precedence
            custom_map = {
                c["name"].lower(): [k.strip().lower() for k in c["keywords"].split(",") if k.strip()]
                for c in custom_categories
            }
            self.categories = {**custom_map, **self.categories}
    
    def analyze_expenses(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        categorized_transactions = self._categorize_transactions(transactions)
        
        analysis = {
            'total_expenses': self._calculate_total_expenses(categorized_transactions),
            'category_breakdown': self._get_category_breakdown(categorized_transactions),
            'monthly_trends': self._calculate_monthly_trends(categorized_transactions),
            'recommendations': self._generate_recommendations(categorized_transactions),
            'top_expenses': self._get_top_expenses(categorized_transactions),
            'subscription_analysis': self._analyze_subscriptions(categorized_transactions)
        }
        
        return analysis
    
    def _categorize_transactions(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for transaction in transactions:
            if transaction.get('category'):
                continue
            if transaction['amount'] >= 0:
                transaction['category'] = 'income'
            else:
                description = transaction['description'].lower()
                transaction['category'] = self._categorize_description(description)
        
        return transactions
    
    def _categorize_description(self, description: str) -> str:
        description = description.replace('&', ' ')
        for category, keywords in self.categories.items():
            for keyword in keywords:
                if keyword in description:
                    return category
        return 'other'
    
    def _calculate_total_expenses(self, transactions: List[Dict[str, Any]]) -> float:
        return sum(abs(t['amount']) for t in transactions if t['amount'] < 0)
    
    def _get_category_breakdown(self, transactions: List[Dict[str, Any]]) -> Dict[str, float]:
        category_totals = defaultdict(float)
        
        for transaction in transactions:
            if transaction['amount'] < 0:
                category_totals[transaction['category']] += abs(transaction['amount'])
        
        return dict(category_totals)
    
    def _calculate_monthly_trends(self, transactions: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        monthly_data = defaultdict(lambda: defaultdict(float))
        
        for transaction in transactions:
            if transaction['amount'] < 0:
                month = transaction['date'][:7]  # YYYY-MM
                category = transaction['category']
                monthly_data[month][category] += abs(transaction['amount'])
        
        return dict(monthly_data)
    
    def _get_top_expenses(self, transactions: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        expenses = [t for t in transactions if t['amount'] < 0]
        return sorted(expenses, key=lambda x: abs(x['amount']), reverse=True)[:limit]
    
    def _analyze_subscriptions(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        recurring = defaultdict(list)
        
        for transaction in transactions:
            if transaction['amount'] < 0 and 'subscription' in transaction['description'].lower():
                recurring[transaction['description']].append(abs(transaction['amount']))
        
        subscription_analysis = {}
        for description, amounts in recurring.items():
            avg_amount = sum(amounts) / len(amounts)
            monthly_cost = avg_amount * 12
            subscription_analysis[description] = {
                'average_amount': avg_amount,
                'annual_cost': monthly_cost,
                'frequency': len(amounts)
            }
        
        return subscription_analysis
    
    def _generate_recommendations(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        recommendations = []
        category_breakdown = self._get_category_breakdown(transactions)
        total_expenses = self._calculate_total_expenses(transactions)
        
        for category, amount in category_breakdown.items():
            percentage = (amount / total_expenses) * 100 if total_expenses > 0 else 0
            
            if category == 'food' and percentage > 15:
                savings_potential = amount * 0.2
                recommendations.append({
                    'category': category,
                    'type': 'reduce_frequency',
                    'message': f"Food expenses are {percentage:.1f}% of your budget. Consider cooking more meals at home.",
                    'potential_savings': savings_potential,
                    'priority': 'high' if percentage > 20 else 'medium'
                })
            
            elif category == 'subscriptions' and amount > 100:
                recommendations.append({
                    'category': category,
                    'type': 'review_subscriptions',
                    'message': f"You spend ${amount:.2f} monthly on subscriptions. Review for unused services.",
                    'potential_savings': amount * 0.3,
                    'priority': 'medium'
                })
            
            elif category == 'entertainment' and percentage > 10:
                savings_potential = amount * 0.25
                recommendations.append({
                    'category': category,
                    'type': 'find_alternatives',
                    'message': f"Entertainment costs are high. Look for free or cheaper alternatives.",
                    'potential_savings': savings_potential,
                    'priority': 'medium'
                })
        
        return sorted(recommendations, key=lambda x: x['potential_savings'], reverse=True)
