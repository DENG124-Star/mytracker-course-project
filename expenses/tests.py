from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from expenses.models import Budget, Category, Expense


class BudgetModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )
        self.category = Category.objects.create(
            user=self.user,
            name="Food"
        )
        self.budget = Budget.objects.create(
            user=self.user,
            month=date.today().month,
            year=date.today().year,
            limit_amount=200
        )
        Expense.objects.create(
            user=self.user,
            category=self.category,
            amount=50,
            currency="USD",
            expense_date=date.today(),
            note="Lunch"
        )

    def test_budget_spent_amount_is_calculated(self):
        spent = self.budget.get_spent_amount()
        self.assertEqual(spent, 50)

    def test_budget_percentage_used_is_calculated(self):
        percentage = self.budget.get_percentage_used()
        self.assertEqual(percentage, 25)

    def test_budget_warning_threshold_false_under_80_percent(self):
        self.assertFalse(self.budget.is_warning_threshold())


class ExpenseModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser2",
            password="testpass123"
        )
        self.category = Category.objects.create(
            user=self.user,
            name="Transport"
        )

    def test_create_expense(self):
        expense = Expense.objects.create(
            user=self.user,
            category=self.category,
            amount=10,
            currency="USD",
            expense_date=date.today(),
            note="Bus ticket"
        )
        self.assertEqual(expense.amount, 10)
        self.assertEqual(expense.currency, "USD")
        self.assertEqual(expense.category.name, "Transport")


class ExpenseViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser3",
            password="testpass123"
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_logged_in_user_can_access(self):
        self.client.login(username="testuser3", password="testpass123")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)