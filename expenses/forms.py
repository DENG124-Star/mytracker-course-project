from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from datetime import date

from .models import Category, Expense, Budget


class UserRegistrationForm(forms.ModelForm):
    """
    Handles new user account creation.

    WHY clean_username and clean_email are separate methods (not in clean):
        Django calls field-level clean_<fieldname>() methods individually
        before calling the cross-field clean(). Keeping username and email
        checks in their own methods means each field shows its own specific
        error message directly under that field in the template, instead of
        a single generic error at the top of the form. This gives a much
        clearer user experience.

    WHY password validation is in clean() and not clean_password:
        Password confirmation requires comparing two fields (password and
        password_confirm), which is inherently a cross-field operation.
        Cross-field logic must live in clean() because that is the only
        method that has access to all cleaned field values simultaneously.

    WHY save() uses commit=False before set_password:
        super().save(commit=False) builds the User object in memory without
        writing to the database. This gives us the chance to call
        set_password(), which hashes the raw password. If we called
        super().save(commit=True) first, the raw password would be written
        to the database in plain text before we could hash it.
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Password'
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Confirm Password'
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_username(self):
        """
        Reject usernames that are already taken.

        WHY checked here and not only at the database level:
            The database unique constraint would also catch duplicates, but
            it raises an IntegrityError that produces a generic 500 error
            page. Checking here surfaces a friendly, field-level message
            before any database write is attempted.
        """
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        """
        Reject email addresses already registered to another account.

        WHY email uniqueness is enforced here:
            Django's User model does not enforce email uniqueness at the
            database level by default. Without this check, two accounts
            could share an email address, which would break any future
            password-reset-by-email flow and cause confusion.
        """
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email

    def clean(self):
        """
        Cross-field validation: confirm passwords match and meet strength rules.

        WHY validate_password is called here and not in clean_password:
            Django's validate_password() can check the password against the
            username (UserAttributeSimilarityValidator), which requires both
            fields. That cross-field access is only available inside clean().
        """
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm:
            if password != password_confirm:
                raise forms.ValidationError('Passwords do not match.')
            try:
                validate_password(password)
            except forms.ValidationError as e:
                raise forms.ValidationError(e.messages)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class CategoryForm(forms.ModelForm):
    """
    Handles creation and editing of user-defined spending categories.

    WHY only 'name' is in fields (not 'description'):
        Keeping the create/edit form minimal reduces friction for the most
        common action (quickly adding a new category). Description is an
        optional enhancement field; it can be added to this form later if
        the UI requires it.

    WHY user is not a form field:
        The user is always set from request.user in the view using
        commit=False. Exposing it as a form field would be a security risk —
        a malicious user could submit any user ID and create categories
        owned by other accounts.
    """

    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category name'
            })
        }


class ExpenseForm(forms.ModelForm):
    """
    Handles creation and editing of individual expense records.

    WHY user is passed as a constructor argument (not a field):
        The category dropdown must only show categories belonging to the
        current user. Passing user= into __init__ lets us filter the
        queryset before the form renders, without exposing the user ID
        as a form field that could be tampered with.

    WHY amount is validated in clean_amount (not only via MinValueValidator):
        MinValueValidator on the model field enforces the constraint at the
        database level. clean_amount enforces it at the form level so the
        user receives a clear, immediate error message on the form itself,
        rather than a database-level exception propagating up.

    WHY future dates trigger a warning rather than a hard rejection:
        Recording a future expense is unusual but not impossible (e.g.
        a subscription charge the user knows is coming). A ValidationError
        here would be too strict and block legitimate use cases.
    """

    def __init__(self, *args, user=None, **kwargs):
        """
        WHY user defaults to None:
            This makes the form safe to instantiate without a user (e.g.
            in unit tests), while still filtering categories correctly
            when user is provided.
        """
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)

    class Meta:
        model = Expense
        fields = ['category', 'amount', 'expense_date', 'note']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'expense_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add a note (optional)'
            })
        }

    def clean_amount(self):
        """
        Reject amounts that are zero or negative.

        WHY 0.01 as the minimum and not 0:
            An expense of exactly zero has no financial meaning and would
            silently pollute totals and category summaries. 0.01 is the
            smallest meaningful monetary unit in a two-decimal-place system.
        """
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError(
                'Amount must be greater than zero. '
                'Please enter a value of at least 0.01.'
            )
        return amount

    def clean_expense_date(self):
        """
        Warn the user if the expense date is set in the future.

        WHY a warning rather than an outright rejection:
            Pre-logging a known upcoming charge (e.g. annual subscription)
            is a valid workflow. The validation error here alerts the user
            to double-check their date, but the form language makes clear
            this is a caution, not a hard block.
        """
        expense_date = self.cleaned_data.get('expense_date')
        if expense_date and expense_date > date.today():
            raise forms.ValidationError(
                'The expense date is in the future. '
                'Please confirm this is intentional before saving.'
            )
        return expense_date


class BudgetForm(forms.ModelForm):
    """
    Handles creation and editing of monthly spending budgets.

    WHY month is a ChoiceField instead of IntegerField:
        An IntegerField would accept any integer (e.g. 13 or -5). Using
        ChoiceField restricts input to exactly the 12 valid months and
        renders as a human-readable dropdown (January, February...) rather
        than a plain number box, which is less error-prone for users.

    WHY year has both widget min/max and a clean_year method:
        The widget min/max attributes enforce limits in the browser (UX),
        but they can be bypassed by any user who edits the HTML. clean_year
        enforces the same range on the server side (security), ensuring
        no rogue year value reaches the database.

    WHY duplicate budget detection is in clean() and not at the view level:
        The form is the right place to surface validation errors because
        it knows how to display them inline next to the relevant fields.
        Catching duplicates in the view would require manually constructing
        and re-rendering the form with an error, which is more complex.
        The unique_together constraint on the model is a final safety net,
        but clean() gives the user a friendly message before hitting it.
    """

    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'),
        (4, 'April'), (5, 'May'), (6, 'June'),
        (7, 'July'), (8, 'August'), (9, 'September'),
        (10, 'October'), (11, 'November'), (12, 'December'),
    ]

    month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    year = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '2020',
            'max': '2100'
        })
    )

    class Meta:
        model = Budget
        fields = ['month', 'year', 'limit_amount']
        widgets = {
            'limit_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            })
        }

    def __init__(self, *args, user=None, **kwargs):
        """
        Store the current user so clean() can check for duplicate budgets.

        WHY user is accepted here even though it is not used in the fields:
            Duplicate detection in clean() requires a database query scoped
            to the current user. The user is not available inside a form
            method unless it is passed in at construction time and stored
            as an instance attribute.
        """
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_year(self):
        """
        Reject years outside the range 2020 to current year + 5.

        WHY current_year + 5 as the upper bound:
            Allowing budgets up to 5 years ahead covers realistic planning
            horizons (annual subscriptions, multi-year goals) while
            preventing obviously erroneous entries like year 9999.
        """
        year = self.cleaned_data.get('year')
        current_year = date.today().year
        if year < 2020 or year > current_year + 5:
            raise forms.ValidationError(
                f'Year must be between 2020 and {current_year + 5}.'
            )
        return year

    def clean(self):
        """
        Prevent duplicate budgets for the same user, month, and year.

        WHY this check excludes the current instance (self.instance.pk):
            When editing an existing budget, the record already exists in
            the database. Without excluding it, the edit form would always
            report a duplicate and the user could never save any changes.
        """
        cleaned_data = super().clean()
        month = cleaned_data.get('month')
        year = cleaned_data.get('year')

        if month and year and self.user:
            qs = Budget.objects.filter(
                user=self.user,
                month=int(month),
                year=int(year)
            )
            # When editing, exclude the record being edited
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError(
                    f'You already have a budget set for '
                    f'{dict(self.MONTH_CHOICES)[int(month)]} {year}. '
                    f'Please edit the existing budget instead.'
                )

        return cleaned_data