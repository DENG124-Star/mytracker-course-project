"""
expenses/services.py
--------------------
Business logic layer for the Personal Expense Tracker.

WHY a separate services.py module exists:
    Django's views are responsible for one thing: receiving an HTTP
    request and returning an HTTP response. When statistical calculations,
    database aggregations, and alert logic all live directly inside view
    functions, the view becomes hard to read, hard to test, and hard to
    reuse. Moving that logic here means:
      - Views stay thin (HTTP in → context out).
      - Each function here can be called from any view, a management
        command, or a test without simulating an HTTP request.
      - The design decision behind each calculation is documented once,
        in one place, rather than scattered across multiple views.
"""

from datetime import date
from decimal import Decimal

from django.db.models import Sum

from .models import Budget, Expense


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_dashboard_stats(user):
    """
    Return all data needed to render the main dashboard for a given user.

    WHY this is a single function and not many small ones:
        The dashboard needs several related pieces of data that all share
        the same month/year anchor (today's date). Calculating them in one
        place avoids repeating the 'today = date.today()' setup and keeps
        all dashboard-specific queries together for easy maintenance.

    WHY we use try/except for Budget.DoesNotExist instead of
    Budget.objects.filter().first():
        get() makes the intent explicit — we expect at most one budget per
        user per month. Using filter().first() would silently return None
        for both 'no budget' and 'multiple budgets', masking a data
        integrity problem. The try/except pattern is the Django convention
        for this exact scenario.

    Returns a dict with keys:
        current_budget, budget_warning, budget_exceeded, spent_amount,
        percentage_used, overrun_reason, recent_expenses,
        monthly_total, category_totals, current_month, current_year
    """
    today = date.today()
    current_month = today.month
    current_year = today.year

    # --- Budget state for the current month ---
    try:
        current_budget = Budget.objects.get(
            user=user,
            month=current_month,
            year=current_year
        )
        budget_warning = current_budget.is_warning_threshold()
        budget_exceeded = current_budget.is_exceeded()
        spent_amount = current_budget.get_spent_amount()
        percentage_used = current_budget.get_percentage_used()
        overrun_reason = (
            get_budget_overrun_reason(current_budget)
            if budget_exceeded else None
        )
    except Budget.DoesNotExist:
        current_budget = None
        budget_warning = False
        budget_exceeded = False
        spent_amount = Decimal('0')
        percentage_used = 0
        overrun_reason = None

    # --- Recent expenses (last 5) ---
    # WHY [:5] and not a filter by date:
    #     The dashboard is a quick-glance summary. Showing the 5 most
    #     recent entries gives the user immediate context regardless of
    #     whether they entered expenses today or a week ago.
    recent_expenses = Expense.objects.filter(user=user)[:5]

    # --- Monthly total spend ---
    monthly_total = (
        Expense.objects
        .filter(user=user,
                expense_date__month=current_month,
                expense_date__year=current_year)
        .aggregate(total=Sum('amount'))['total']
        or Decimal('0')
    )

    # --- Spend broken down by category for current month ---
    # WHY order_by('-total'):
    #     Showing the highest-spending category first lets users
    #     immediately spot where most of their money is going.
    category_totals = (
        Expense.objects
        .filter(user=user,
                expense_date__month=current_month,
                expense_date__year=current_year)
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    return {
        'current_budget': current_budget,
        'budget_warning': budget_warning,
        'budget_exceeded': budget_exceeded,
        'spent_amount': spent_amount,
        'percentage_used': percentage_used,
        'overrun_reason': overrun_reason,
        'recent_expenses': recent_expenses,
        'monthly_total': monthly_total,
        'category_totals': category_totals,
        'current_month': current_month,
        'current_year': current_year,
    }


# ---------------------------------------------------------------------------
# Monthly Summary
# ---------------------------------------------------------------------------

def get_monthly_summary_stats(user, month, year):
    """
    Return all data needed to render the monthly summary page.

    WHY month and year are passed in as arguments instead of read from
    date.today() inside this function:
        The summary page allows the user to browse any historical month,
        not just the current one. Accepting month/year as parameters makes
        this function reusable for any period and easy to test with fixed
        dates.

    Returns a dict with keys:
        expenses, total, category_totals, category_trend,
        budget, budget_spent, budget_percentage, budget_warning,
        budget_exceeded, overrun_reason
    """
    # --- All expenses for the selected month ---
    expenses = (
        Expense.objects
        .filter(user=user,
                expense_date__month=month,
                expense_date__year=year)
        .order_by('-expense_date')
    )

    total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # --- Spending by category ---
    category_totals = (
        expenses
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    # --- Category trend vs. previous month ---
    category_trend = get_category_trend(user, month, year)

    # --- Budget for the selected month ---
    try:
        budget = Budget.objects.get(user=user, month=month, year=year)
        budget_spent = budget.get_spent_amount()
        budget_percentage = budget.get_percentage_used()
        budget_warning = budget.is_warning_threshold()
        budget_exceeded = budget.is_exceeded()
        overrun_reason = (
            get_budget_overrun_reason(budget) if budget_exceeded else None
        )
    except Budget.DoesNotExist:
        budget = None
        budget_spent = Decimal('0')
        budget_percentage = 0
        budget_warning = False
        budget_exceeded = False
        overrun_reason = None

    return {
        'expenses': expenses,
        'total': total,
        'category_totals': category_totals,
        'category_trend': category_trend,
        'budget': budget,
        'budget_spent': budget_spent,
        'budget_percentage': budget_percentage,
        'budget_warning': budget_warning,
        'budget_exceeded': budget_exceeded,
        'overrun_reason': overrun_reason,
    }


# ---------------------------------------------------------------------------
# Budget List
# ---------------------------------------------------------------------------

def get_budget_list_annotated(user):
    """
    Return all budgets for a user, each annotated with live spend data.

    WHY this loop is in services and not in the template or view:
        Templates should not call methods that hit the database. Calling
        budget.get_spent_amount() inside a template loop would fire one
        SQL query per budget row (N+1 problem). Doing it here in Python
        makes it explicit and easy to spot and optimise later (e.g. by
        replacing the loop with a single annotated queryset).

    WHY we attach attributes directly to each budget object:
        This avoids creating a parallel data structure (e.g. a list of
        dicts) that the template would have to be rewritten to consume.
        The template can keep using {{ budget.spent }}, {{ budget.warning }}
        etc., and only this function needs to change if the logic changes.

    Returns a list of Budget objects with extra attributes:
        .spent, .percentage, .warning, .exceeded
    """
    budgets = Budget.objects.filter(user=user).order_by('-year', '-month')

    for budget in budgets:
        budget.spent = budget.get_spent_amount()
        budget.percentage = budget.get_percentage_used()
        budget.warning = budget.is_warning_threshold()
        budget.exceeded = budget.is_exceeded()

    return budgets


# ---------------------------------------------------------------------------
# Category Trend  (NEW — MOD 3)
# ---------------------------------------------------------------------------

def get_category_trend(user, month, year):
    """
    Compare per-category spending between the given month and the previous
    month, returning a list sorted by this month's total (highest first).

    WHY we compare to the previous month rather than the same month last year:
        For a personal expense tracker, users care most about short-term
        behaviour change — did I spend more on food this month than last
        month? Year-over-year comparison is more relevant for business
        analytics. Month-over-month is simpler and more immediately
        actionable for personal finance.

    WHY we use Python to merge the two querysets rather than a SQL JOIN:
        Django's ORM does not natively support a FULL OUTER JOIN across
        two aggregated querysets. Merging in Python keeps the code
        readable and avoids raw SQL, which would reduce portability across
        database backends.

    Returns a list of dicts, each with:
        category_name (str)
        this_month    (Decimal) — total spend in the requested month
        last_month    (Decimal) — total spend in the preceding month
        change        (Decimal) — this_month minus last_month
        trend         (str)     — 'up', 'down', or 'same'
    """
    # Handle January → December crossover correctly
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year

    this_month_qs = (
        Expense.objects
        .filter(user=user,
                expense_date__month=month,
                expense_date__year=year)
        .values('category__name')
        .annotate(total=Sum('amount'))
    )

    last_month_qs = (
        Expense.objects
        .filter(user=user,
                expense_date__month=prev_month,
                expense_date__year=prev_year)
        .values('category__name')
        .annotate(total=Sum('amount'))
    )

    this_month_map = {r['category__name']: r['total'] for r in this_month_qs}
    last_month_map = {r['category__name']: r['total'] for r in last_month_qs}

    all_categories = set(this_month_map.keys()) | set(last_month_map.keys())

    trend_rows = []
    for name in all_categories:
        this_total = this_month_map.get(name, Decimal('0'))
        last_total = last_month_map.get(name, Decimal('0'))
        change = this_total - last_total

        if change > 0:
            trend = 'up'
        elif change < 0:
            trend = 'down'
        else:
            trend = 'same'

        trend_rows.append({
            'category_name': name,
            'this_month': this_total,
            'last_month': last_total,
            'change': change,
            'trend': trend,
        })

    trend_rows.sort(key=lambda r: r['this_month'], reverse=True)
    return trend_rows


# ---------------------------------------------------------------------------
# Budget Overrun Reason  (NEW — MOD 3)
# ---------------------------------------------------------------------------

def get_budget_overrun_reason(budget):
    """
    Return a human-readable explanation of why a budget has been exceeded.

    WHY this returns a plain string instead of a structured object:
        The result is only used to display a message in a template. A plain
        string is the simplest format for that use case. If this ever needs
        to drive automated alerts or API responses, it can be refactored
        to return a structured dict at that point.

    WHY we identify the top overspending category:
        Simply saying "you went over budget" is not actionable. Telling
        the user which category drove the overrun gives them a concrete
        area to address, making the warning genuinely useful.

    Args:
        budget: A Budget instance confirmed as exceeded (is_exceeded() True).

    Returns:
        str — a sentence describing the primary reason for the overrun.
    """
    spent = budget.get_spent_amount()
    over_by = spent - budget.limit_amount

    top_category = (
        Expense.objects
        .filter(user=budget.user,
                expense_date__month=budget.month,
                expense_date__year=budget.year)
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
        .first()
    )

    if top_category:
        cat_name = top_category['category__name']
        cat_total = top_category['total']
        cat_pct = (
            (cat_total / budget.limit_amount) * 100
            if budget.limit_amount > 0 else 0
        )
        return (
            f"Budget exceeded by ${over_by:.2f}. "
            f"'{cat_name}' is your largest expense category this month "
            f"(${cat_total:.2f}, {cat_pct:.0f}% of your budget limit)."
        )

    return f"Budget exceeded by ${over_by:.2f}."
