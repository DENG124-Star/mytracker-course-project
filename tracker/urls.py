from django.urls import path
from . import views

app_name = "tracker"

urlpatterns = [
    path("", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("add/", views.add_expense_view, name="add_expense"),
    path("history/", views.expense_list_view, name="expense_list"),
]