from django.shortcuts import render
from datetime import date

def login_view(request):
    return render(request, "tracker/login.html")

def register_view(request):
    return render(request, "tracker/register.html")

def dashboard_view(request):
    today = date.today()

    context = {
        "month_name": today.strftime("%B"),
        "monthly_total": 450.00,
        "budget_percent": 90,
        "budget_limit": 500.00,
        "top_category_name": "Food & Dining",
        "top_category_percent": 40,
    }
    return render(request, "tracker/dashboard.html", context)

def add_expense_view(request):
    context = {
        "categories": [
            "Food & Dining",
            "Transport",
            "Shopping",
            "Bills",
            "Entertainment",
        ]
    }
    return render(request, "tracker/add_expense.html", context)

def expense_list_view(request):
    context = {
        "expenses": [
            {"date": "12 Feb", "category": "Food", "note": "Lunch", "amount": "£12.50"},
            {"date": "11 Feb", "category": "Transport", "note": "Bus", "amount": "£2.50"},
            {"date": "10 Feb", "category": "Food", "note": "Coffee", "amount": "£4.20"},
        ]
    }
    return render(request, "tracker/expense_list.html", context)