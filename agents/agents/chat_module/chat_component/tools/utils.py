def format_currency(amount, currency='USD'):
    """Format amount as currency"""
    return f"{currency} {amount:.2f}"

def calculate_percentage(amount, percentage):
    """Calculate percentage of amount"""
    return (amount * percentage) / 100

def round_to_cents(amount):
    """Round amount to 2 decimal places"""
    return round(amount, 2)