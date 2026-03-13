from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class Category(models.Model):
    """
    Represents a user-defined spending category (e.g. Food, Transport).

    WHY unique_together on [user, name]:
        Each user owns their own category namespace. Two different users
        can both have a category called 'Food' without conflict, but a
        single user cannot create duplicate category names. This enforces
        data integrity at the database level, not just the form level.

    WHY description is optional (blank=True, null=True):
        Categories are quick to create — forcing a description would slow
        down the user's workflow for simple cases. It is provided as an
        enhancement field for users who want to document their categories.
    """
    category_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    name = models.CharField(max_length=100)
    description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text='Optional: describe what expenses belong in this category.'
    )

    class Meta:
        verbose_name_plural = 'Categories'
        unique_together = ['user', 'name']

    def __str__(self):
        return self.name


class Expense(models.Model):
    """
    Records a single spending event tied to a user and category.

    WHY MinValueValidator(0.01) on amount:
        An expense of zero or a negative value is logically meaningless
        in this context. Enforcing a minimum of 0.01 at the model level
        ensures this constraint is applied regardless of which form or
        API endpoint creates the record.

    WHY currency defaults to 'USD' with max_length=3:
        ISO 4217 currency codes are exactly 3 characters (USD, GBP, KES).
        Defaulting to USD keeps backward compatibility with existing data
        while opening the door to multi-currency support in the future
        without requiring a schema redesign.

    WHY ordering by [-expense_date, -created_at]:
        Users most commonly want to see the most recent expense first.
        Using two fields ensures stable ordering when multiple expenses
        share the same date (created_at acts as a tiebreaker).
    """
    expense_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text='ISO 4217 currency code, e.g. USD, GBP, KES.'
    )
    expense_date = models.DateField()
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.currency} {self.amount} ({self.expense_date})"


class Budget(models.Model):
    """
    Defines a spending limit for a user over a specific month and year.

    WHY unique_together on [user, month, year]:
        A user should only have one budget per calendar period. Allowing
        multiple budgets for the same month would make the warning and
        summary logic ambiguous — which limit applies? The constraint
        enforces a clean one-budget-per-period model at the database level.

    WHY period_type defaults to 'monthly':
        The current UI and summary logic is built around monthly cycles.
        Introducing period_type as a field now means weekly budgets can be
        supported in the future by extending the choices and adjusting the
        date-filter logic, without any schema change.

    WHY MinValueValidator(0.01) on limit_amount:
        A budget of zero or less has no practical meaning and would cause
        division-by-zero errors in get_percentage_used(). The validator
        prevents this at the model level before any calculation runs.
    """

    PERIOD_CHOICES = [
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
    ]

    budget_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='budgets'
    )
    month = models.IntegerField()   # 1–12
    year = models.IntegerField()
    limit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    period_type = models.CharField(
        max_length=10,
        choices=PERIOD_CHOICES,
        default='monthly',
        help_text='Cycle for this budget. Currently monthly is fully supported.'
    )

    class Meta:
        unique_together = ['user', 'month', 'year']

    def __str__(self):
        return (
            f"{self.user.username} - {self.month}/{self.year}: "
            f"${self.limit_amount} ({self.get_period_type_display()})"
        )

    def get_spent_amount(self):
        """
        Return the total amount spent by this user in this budget period.

        WHY this lives on the model and not in views:
            The Budget model owns the concept of a budget period (month +
            year). Placing the spent-amount calculation here means every
            part of the system — views, templates, the shell — can ask a
            Budget object how much was spent without duplicating the query.
        """
        from django.db.models import Sum
        total = self.user.expenses.filter(
            expense_date__month=self.month,
            expense_date__year=self.year
        ).aggregate(total=Sum('amount'))['total']
        return total or 0

    def get_percentage_used(self):
        """
        Return the percentage of this budget that has been spent (0–N%).

        WHY we guard against limit_amount <= 0:
            Even with MinValueValidator in place, defensive programming
            here prevents a ZeroDivisionError if a budget object is
            constructed outside of a validated form (e.g. in tests or
            via the shell).
        """
        spent = self.get_spent_amount()
        if self.limit_amount > 0:
            return (spent / self.limit_amount) * 100
        return 0

    def is_warning_threshold(self):
        """
        Return True if spending has reached or exceeded 80% of the budget.

        WHY 80% as the threshold:
            80% gives the user an early signal while they still have room
            to adjust behaviour before the month ends. This is a widely
            used convention in personal finance tools (similar to credit
            card alert thresholds). The value is intentionally defined
            here in one place so it can be changed globally without
            hunting through templates or views.
        """
        return self.get_percentage_used() >= 80

    def is_exceeded(self):
        """
        Return True if total spending has gone over the budget limit.

        WHY separate from is_warning_threshold:
            Warning and exceeded are two distinct states that drive
            different UI messages. Keeping them as separate methods
            makes the template logic straightforward:
            if exceeded → red alert; elif warning → yellow alert.
        """
        return self.get_spent_amount() > self.limit_amount