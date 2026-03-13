from django.contrib import admin
from .models import Category, Expense, Budget


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['category_id', 'user', 'name', 'description']
    list_filter = ['user']
    search_fields = ['name', 'user__username']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['expense_id', 'user', 'category', 'amount', 'currency', 'expense_date', 'created_at']
    list_filter = ['user', 'category', 'currency', 'expense_date']
    search_fields = ['note', 'user__username']
    date_hierarchy = 'expense_date'


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['budget_id', 'user', 'month', 'year', 'limit_amount', 'period_type']
    list_filter = ['user', 'year', 'month', 'period_type']