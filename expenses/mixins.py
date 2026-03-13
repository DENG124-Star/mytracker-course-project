"""
expenses/mixins.py
------------------
Reusable view helpers for the Personal Expense Tracker.

WHY this module exists:
    The create and update views for Category, Expense, and Budget all
    follow an identical pattern:

        GET  → instantiate form (with optional instance) → render template
        POST → bind form → validate → save → redirect with success message
                                   → re-render form with errors on failure

    Writing this pattern six times (category_create, category_update,
    expense_create, expense_update, budget_create, budget_update) produces
    ~60 lines of near-identical code. Any bug fix or behaviour change
    (e.g. adding logging, changing how errors are shown) must be applied
    in six places instead of one.

    Extracting the pattern into handle_form_view() means:
      - Each view becomes 3-5 lines that express only what is unique to it.
      - The shared logic is tested and changed in exactly one place.
      - The code hierarchy is clearer: views handle HTTP routing,
        this module handles the form lifecycle.
"""

from django.contrib import messages
from django.shortcuts import redirect, render


def handle_form_view(
    request,
    form_class,
    template,
    success_url,
    success_msg,
    instance=None,
    extra_context=None,
    form_kwargs=None,
):
    """
    Handle the full create/update lifecycle for a model-backed form view.

    This function encapsulates the POST/GET/validate/save/redirect pattern
    that is repeated across all create and update views in this project.

    WHY instance defaults to None:
        Passing instance=None means the form creates a new object (CREATE).
        Passing a model instance means the form pre-fills with that object's
        data (UPDATE). Django's ModelForm handles both cases identically
        through its instance parameter, so one helper covers both modes.

    WHY extra_context is a dict and not **kwargs:
        Using a dedicated dict parameter makes it explicit that extra data
        is being added to the template context. It also avoids conflicts
        with Python's own keyword argument namespace and makes the call
        sites easier to read at a glance.

    WHY form_kwargs is a separate dict and not merged into extra_context:
        form_kwargs are passed to the form constructor, not to the template.
        Keeping them separate prevents accidental name collisions between
        form constructor parameters and template context variables.

    WHY we call form.save(commit=False) in the view, not here:
        handle_form_view is a generic helper that does not know which model
        field (e.g. user) needs to be injected before the final save. The
        caller is responsible for that step via the pre_save callback.
        This keeps the helper truly generic and free of model-specific
        knowledge.

    Args:
        request       (HttpRequest)  : The current HTTP request.
        form_class    (type)         : The ModelForm class to instantiate.
        template      (str)          : Template path to render on GET or invalid POST.
        success_url   (str)          : Named URL to redirect to after a successful save.
        success_msg   (str)          : Flash message shown after a successful save.
        instance      (Model|None)   : Existing model instance for UPDATE, or None
                                       for CREATE. Default: None.
        extra_context (dict|None)    : Additional variables to pass to the template.
                                       Default: None.
        form_kwargs   (dict|None)    : Extra keyword arguments forwarded to the form
                                       constructor (e.g. user=request.user for forms
                                       that need to filter querysets by user).
                                       Default: None.

    Returns:
        HttpResponse — either a redirect (on success) or a rendered template.
    """
    form_kwargs = form_kwargs or {}
    extra_context = extra_context or {}

    if request.method == 'POST':
        form = form_class(request.POST, instance=instance, **form_kwargs)
        if form.is_valid():
            form.save()
            messages.success(request, success_msg)
            return redirect(success_url)
    else:
        form = form_class(instance=instance, **form_kwargs)

    context = {'form': form}
    context.update(extra_context)
    return render(request, template, context)
