# Personal Expense Tracker

A Django-based web application for tracking personal expenses, designed for students and young professionals.

## Features

- **User Authentication**: Register, login, and logout functionality
- **Expense Tracking**: Add, edit, and delete expenses with categories
- **Budget Management**: Set monthly budgets with 80% warning threshold
- **Category Organization**: Create custom categories for expenses
- **Filtering**: Filter expenses by date range, category, month, and year
- **Monthly Summaries**: View detailed monthly spending breakdowns
- **Budget Warnings**: Get notified when spending reaches 80% of budget

## Tech Stack

- **Backend**: Django 4.2
- **Database**: SQLite (default), PostgreSQL supported
- **Frontend**: Django templates with modern CSS

## Installation

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate the virtual environment:
```bash
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Create a superuser (optional, for admin access):
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

7. Open your browser and go to `http://127.0.0.1:8000`

## Usage

1. **Register** a new account or login
2. **Create categories** to organize your expenses (e.g., Food, Transport, Entertainment)
3. **Set a budget** for the current month
4. **Add expenses** as you spend
5. **View dashboard** for an overview of your finances
6. **Check monthly summary** for detailed breakdowns

## Project Structure

```
expense_tracker/
├── expense_tracker/          # Project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── expenses/                 # Main application
│   ├── models.py            # Category, Expense, Budget models
│   ├── views.py             # All views
│   ├── forms.py             # Forms for user input
│   ├── urls.py              # URL routing
│   └── admin.py             # Admin configuration
├── templates/               # HTML templates
│   ├── base.html
│   ├── registration/
│   └── expenses/
├── static/
│   └── css/style.css        # Stylesheet
├── manage.py
└── requirements.txt
```

## Database Models

- **User**: Django's built-in User model
- **Category**: User-specific expense categories
- **Expense**: Individual expense records
- **Budget**: Monthly budget limits

## License

MIT License
