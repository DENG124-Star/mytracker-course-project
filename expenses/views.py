"""
expenses/views.py
-----------------
HTTP request handlers for the Personal Expense Tracker.

Design principle — views are kept intentionally thin:
    Each view is responsible for exactly two things:
      1. Extracting input from the HTTP request (query params, POST data, URL kwargs).
      2. Returning an HTTP response (redirect or rendered template).

    All business logic (calculations, aggregations, alert decisions) lives in
    services.py. All repeated form-lifecycle logic lives in mixins.py.
    This separation makes each layer easier to read, test, and change
    independently.
"""

from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BudgetForm, CategoryForm, ExpenseForm, UserRegistrationForm
from .mixins import handle_form_view
from .models import Budget, Category, Expense
from .services import (
    get_budget_list_annotated,
    get_dashboard_stats,
    get_monthly_summary_stats,
)


# ---------------------------------------------------------------------------
# Authentication Views
# ---------------------------------------------------------------------------

def register(request):
    """
    Handle new user registration.

    WHY we redirect authenticated users immediately:
        An already-logged-in user who lands on /register/ has likely
        arrived by mistake (e.g. a stale bookmark). Redirecting them to
        the dashboard avoids confusion and prevents creating duplicate
        accounts.

    WHY we call login() immediately after save():
        After a successful registration the user expects to be inside the
        app, not sent back to a login form. Logging them in automatically
        removes friction and is the standard UX convention for sign-up
        flows.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()

    return render(request, 'registration/register.html', {'form': form})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    """
    Render the main dashboard with budget status and spending summary.

    WHY @login_required on every non-auth view:
        Financial data is personal and sensitive. Every view that touches
        expense, budget, or category data must be gated behind authentication.
        Using the decorator (rather than checking request.user.is_authenticated
        manually) is the Django convention — it redirects unauthenticated
        users to LOGIN_URL automatically and keeps the view body clean.

    WHY we delegate all calculation to get_dashboard_stats():
        The view's only job is to call the service and pass the result to
        the template. This keeps the view testable without an HTTP client
        and ensures the dashboard logic can be reused (e.g. in an API
        endpoint) without duplicating queries.
    """
    context = get_dashboard_stats(request.user)
    return render(request, 'expenses/dashboard.html', context)


# ---------------------------------------------------------------------------
# Category Views
# ---------------------------------------------------------------------------

@login_required
def category_list(request):
    """
    Display all categories belonging to the current user.

    WHY we filter by user:
        Categories are user-scoped. Without this filter, every user would
        see every other user's categories, which would be a data privacy
        violation and would break the unique-category-name guarantee.
    """
    categories = Category.objects.filter(user=request.user)
    return render(request, 'expenses/category_list.html', {'categories': categories})


@login_required
def category_create(request):
    """
    Create a new category owned by the current user.

    WHY we use commit=False before saving:
        CategoryForm only exposes the 'name' field — it deliberately does
        not expose 'user', because the user must always be set to the
        currently authenticated user and should never come from form input.
        commit=False lets us inject request.user before the INSERT runs.
    """
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, 'Category created successfully!')
            return redirect('category_list')
    else:
        form = CategoryForm()

    return render(request, 'expenses/category_form.html', {
        'form': form,
        'title': 'Add Category',
    })


@login_required
def category_update(request, pk):
    """
    Update an existing category owned by the current user.

    WHY get_object_or_404 with both pk AND user:
        Fetching by pk alone would allow a user to edit another user's
        category by guessing the numeric ID (Insecure Direct Object
        Reference). Adding user=request.user to the lookup ensures the
        object 404s if it does not belong to the requester.

    WHY we use handle_form_view here (and not in category_create):
        Update views always have an existing instance — user ownership is
        already established in the get_object_or_404 call, so no
        commit=False injection is needed. handle_form_view handles the
        full POST/GET/validate/save/redirect cycle cleanly.
    """
    category = get_object_or_404(Category, pk=pk, user=request.user)
    return handle_form_view(
        request,
        form_class=CategoryForm,
        template='expenses/category_form.html',
        success_url='category_list',
        success_msg='Category updated successfully!',
        instance=category,
        extra_context={'title': 'Edit Category'},
    )


@login_required
def category_delete(request, pk):
    """
    Delete a category after explicit POST confirmation.

    WHY we require a POST and not just a GET with ?confirm=1:
        Deletion via GET is vulnerable to CSRF attacks through prefetching
        or link-following. A POST with Django's CSRF token ensures the
        deletion is intentional and originated from our own form.
    """
    category = get_object_or_404(Category, pk=pk, user=request.user)

    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted successfully!')
        return redirect('category_list')

    return render(request, 'expenses/category_confirm_delete.html', {
        'category': category,
    })


# ---------------------------------------------------------------------------
# Expense Views
# ---------------------------------------------------------------------------

@login_required
def expense_list(request):
    """
    Display all expenses for the current user, with optional filters.

    WHY we support both date-range filters AND month/year filters:
        Date-range filters (start_date, end_date) support precise custom
        queries. Month/year filters support the common case of reviewing
        a complete calendar month. Providing both gives users flexibility
        without forcing them to calculate month boundaries manually.

    WHY we compute the total inside the view (not the template):
        Templates should not run database queries. Aggregating here and
        passing 'total' as context keeps the template logic pure display.
    """
    expenses = Expense.objects.filter(user=request.user)

    start_date = request.GET.get('start_date')
    end_date   = request.GET.get('end_date')
    category_id = request.GET.get('category')
    month      = request.GET.get('month')
    year       = request.GET.get('year')

    if start_date:
        expenses = expenses.filter(expense_date__gte=start_date)
    if end_date:
        expenses = expenses.filter(expense_date__lte=end_date)
    if category_id:
        expenses = expenses.filter(category_id=category_id)
    if month:
        expenses = expenses.filter(expense_date__month=month)
    if year:
        expenses = expenses.filter(expense_date__year=year)

    total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    categories = Category.objects.filter(user=request.user)

    return render(request, 'expenses/expense_list.html', {
        'expenses': expenses,
        'categories': categories,
        'total': total,
        'filter_start_date': start_date,
        'filter_end_date': end_date,
        'filter_category': category_id,
        'filter_month': month,
        'filter_year': year,
    })


@login_required
def expense_create(request):
    """
    Create a new expense for the current user.

    WHY we guard against an empty category list before rendering the form:
        ExpenseForm requires a category selection. If the user has no
        categories yet, the form will render with an empty dropdown and
        any submission will fail with a confusing validation error. A
        proactive redirect with a clear message is far better UX than
        a broken form.

    WHY we use commit=False before saving:
        ExpenseForm does not expose 'user' as a field (same reason as
        CategoryForm). commit=False lets us attach request.user to the
        unsaved instance before the INSERT executes.

    WHY we set expense_date initial to today:
        The most common case is recording an expense that just happened.
        Pre-filling today's date saves the user a click in the typical
        workflow.
    """
    if not Category.objects.filter(user=request.user).exists():
        messages.warning(
            request,
            'You need to create a category before adding an expense.'
        )
        return redirect('category_create')

    if request.method == 'POST':
        form = ExpenseForm(request.POST, user=request.user)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            messages.success(request, 'Expense added successfully!')
            return redirect('expense_list')
    else:
        form = ExpenseForm(user=request.user)
        form.initial['expense_date'] = date.today()

    return render(request, 'expenses/expense_form.html', {
        'form': form,
        'title': 'Add Expense',
    })


@login_required
def expense_update(request, pk):
    """
    Update an existing expense owned by the current user.

    WHY we pass user via form_kwargs:
        ExpenseForm filters the category queryset to show only the
        current user's categories. Passing user= through form_kwargs
        is the clean way to supply constructor arguments that are not
        part of the standard ModelForm interface.
    """
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    return handle_form_view(
        request,
        form_class=ExpenseForm,
        template='expenses/expense_form.html',
        success_url='expense_list',
        success_msg='Expense updated successfully!',
        instance=expense,
        extra_context={'title': 'Edit Expense'},
        form_kwargs={'user': request.user},
    )


@login_required
def expense_delete(request, pk):
    """Delete an expense after explicit POST confirmation."""
    expense = get_object_or_404(Expense, pk=pk, user=request.user)

    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully!')
        return redirect('expense_list')

    return render(request, 'expenses/expense_confirm_delete.html', {
        'expense': expense,
    })


# ---------------------------------------------------------------------------
# Budget Views
# ---------------------------------------------------------------------------

@login_required
def budget_list(request):
    """
    Display all budgets for the current user, annotated with live spend data.

    WHY we delegate annotation to get_budget_list_annotated():
        Calling model methods in a template loop fires one SQL query per
        budget row (N+1 problem). Doing the annotation in the service
        layer makes the cost visible and easy to optimise later.
    """
    budgets = get_budget_list_annotated(request.user)
    return render(request, 'expenses/budget_list.html', {'budgets': budgets})


@login_required
def budget_create(request):
    """
    Create a new monthly budget for the current user.

    WHY we wrap save() in try/except IntegrityError:
        The Budget model enforces unique_together on [user, month, year].
        If the user submits a duplicate budget (e.g. by opening two tabs),
        the database will raise an IntegrityError. Catching it here and
        showing a friendly message prevents an unhandled 500 error.

    WHY BudgetForm.clean() also checks for duplicates:
        Form-level validation catches duplicates before any database call
        and shows the error inline on the form. The IntegrityError catch
        here is a second line of defence against race conditions where two
        requests pass form validation simultaneously before either saves.

    WHY we pre-fill month and year with today's values:
        The most common use case is creating a budget for the current month.
        Pre-filling reduces the number of fields the user must interact with.
    """
    if request.method == 'POST':
        form = BudgetForm(request.POST)
        if form.is_valid():
            try:
                budget = form.save(commit=False)
                budget.user = request.user
                budget.save()
                messages.success(request, 'Budget created successfully!')
                return redirect('budget_list')
            except IntegrityError:
                messages.error(
                    request,
                    'A budget for that month and year already exists.'
                )
    else:
        form = BudgetForm()
        form.initial['month'] = date.today().month
        form.initial['year']  = date.today().year

    return render(request, 'expenses/budget_form.html', {
        'form': form,
        'title': 'Add Budget',
    })


@login_required
def budget_update(request, pk):
    """
    Update an existing budget owned by the current user.

    WHY we use handle_form_view here (and not in budget_create):
        The update case already has an instance — user ownership is
        confirmed by get_object_or_404. No commit=False injection or
        IntegrityError guard is needed because the unique constraint
        allows updating a record to its own (month, year) values.
    """
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    return handle_form_view(
        request,
        form_class=BudgetForm,
        template='expenses/budget_form.html',
        success_url='budget_list',
        success_msg='Budget updated successfully!',
        instance=budget,
        extra_context={'title': 'Edit Budget'},
    )


@login_required
def budget_delete(request, pk):
    """Delete a budget after explicit POST confirmation."""
    budget = get_object_or_404(Budget, pk=pk, user=request.user)

    if request.method == 'POST':
        budget.delete()
        messages.success(request, 'Budget deleted successfully!')
        return redirect('budget_list')

    return render(request, 'expenses/budget_confirm_delete.html', {
        'budget': budget,
    })


# ---------------------------------------------------------------------------
# Monthly Summary
# ---------------------------------------------------------------------------

@login_required
def monthly_summary(request):
    """
    Display a detailed summary for a selected month, including category
    trend comparison against the previous month.

    WHY we parse and validate month/year in the view and not in the service:
        Parsing HTTP query parameters is an HTTP concern, not a business
        logic concern. The service function accepts clean integers; the
        view is responsible for turning raw strings into those integers
        and handling bad input gracefully.

    WHY we fall back to today's month/year on invalid input:
        A user who manually edits the URL (e.g. ?month=abc) should see
        a sensible page, not a 500 error. Falling back silently keeps the
        experience smooth.
    """
    try:
        year  = int(request.GET.get('year',  date.today().year))
        month = int(request.GET.get('month', date.today().month))
    except (ValueError, TypeError):
        year  = date.today().year
        month = date.today().month

    stats = get_monthly_summary_stats(request.user, month, year)

    context = {
        **stats,
        'month': month,
        'year':  year,
    }
    return render(request, 'expenses/monthly_summary.html', context)
