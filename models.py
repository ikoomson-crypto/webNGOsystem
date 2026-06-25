from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoices = db.relationship('Invoice', backref='user', lazy=True)
    expenses = db.relationship('Expense', backref='user', lazy=True)
    journal_entries = db.relationship('JournalEntry', backref='user', lazy=True)
    purchases = db.relationship('Purchase', backref='user', lazy=True)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    invoices = db.relationship('Invoice', backref='category', lazy=True)
    expenses = db.relationship('Expense', backref='category', lazy=True)
    purchases = db.relationship('Purchase', backref='category', lazy=True)


class AccountType(db.Model):
    """Account types like Asset, Liability, Equity, Revenue, Expense"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    normal_balance = db.Column(db.String(10))  # Debit or Credit

    accounts = db.relationship('ChartOfAccount', backref='account_type', lazy=True)


class ChartOfAccount(db.Model):
    """Individual accounts in the chart of accounts"""
    id = db.Column(db.Integer, primary_key=True)
    account_code = db.Column(db.String(20), unique=True, nullable=False)
    account_name = db.Column(db.String(100), nullable=False)
    account_type_id = db.Column(db.Integer, db.ForeignKey('account_type.id'), nullable=False)
    description = db.Column(db.String(200))
    balance = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    journal_entries = db.relationship('JournalEntry', backref='account', lazy=True)


class Supplier(db.Model):
    """Supplier/Vendor information"""
    id = db.Column(db.Integer, primary_key=True)
    supplier_code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    tax_id = db.Column(db.String(50))
    payment_terms = db.Column(db.String(50), default='Net 30')
    opening_balance = db.Column(db.Float, default=0.0)
    current_balance = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    purchases = db.relationship('Purchase', backref='supplier', lazy=True)


class Customer(db.Model):
    """Customer information"""
    id = db.Column(db.Integer, primary_key=True)
    customer_code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    tax_id = db.Column(db.String(50))
    credit_limit = db.Column(db.Float, default=0.0)
    opening_balance = db.Column(db.Float, default=0.0)
    current_balance = db.Column(db.Float, default=0.0)
    payment_terms = db.Column(db.String(50), default='Net 30')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class JournalEntry(db.Model):
    """Journal entries for double-entry accounting"""
    __tablename__ = 'journal_entry'
    id = db.Column(db.Integer, primary_key=True)
    entry_number = db.Column(db.String(50), unique=True, nullable=False,
                             default=lambda: JournalEntry.generate_entry_number())
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    account_id = db.Column(db.Integer, db.ForeignKey('chart_of_account.id'), nullable=False)
    debit = db.Column(db.Float, default=0.0)
    credit = db.Column(db.Float, default=0.0)
    reference_type = db.Column(db.String(50))
    reference_id = db.Column(db.Integer)
    attachment_filename = db.Column(db.String(255))
    attachment_original_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    @staticmethod
    def generate_entry_number():
        """Generate a unique entry number"""
        import uuid
        from datetime import datetime as dt

        timestamp = dt.now().strftime('%Y%m%d%H%M%S%f')[:-3]
        unique_id = uuid.uuid4().hex[:12].upper()
        return f"JE-{timestamp}-{unique_id}"

class Purchase(db.Model):
    """Purchase orders/invoices from suppliers"""
    id = db.Column(db.Integer, primary_key=True)
    purchase_number = db.Column(db.String(50), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    invoice_number = db.Column(db.String(50))
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='Pending')  # Pending, Paid, Overdue
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PaymentVoucher(db.Model):
    """Payment voucher for supplier payments"""
    id = db.Column(db.Integer, primary_key=True)
    voucher_number = db.Column(db.String(50), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    exchange_rate = db.Column(db.Float, default=1.0)
    date = db.Column(db.Date, nullable=False)
    debit_account_id = db.Column(db.Integer, db.ForeignKey('chart_of_account.id'), nullable=False)
    gross_amount = db.Column(db.Float, nullable=False)
    wht_amount = db.Column(db.Float, default=0.0)
    vat_amount = db.Column(db.Float, default=0.0)
    net_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Pending')
    reference_number = db.Column(db.String(100))
    attachment_filename = db.Column(db.String(255))
    attachment_original_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relationships
    supplier = db.relationship('Supplier', backref='payment_vouchers', lazy=True)
    debit_account = db.relationship('ChartOfAccount', foreign_keys=[debit_account_id], backref='payment_vouchers',
                                    lazy=True)
    user = db.relationship('User', backref='payment_vouchers', lazy=True)

class PaymentVoucherLine(db.Model):
    """Individual line items for payment voucher"""
    id = db.Column(db.Integer, primary_key=True)
    payment_voucher_id = db.Column(db.Integer, db.ForeignKey('payment_voucher.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    wht_rate = db.Column(db.Float, default=0.0)
    vat_rate = db.Column(db.Float, default=0.0)
    gross_amount = db.Column(db.Float, nullable=False)
    wht_amount = db.Column(db.Float, default=0.0)
    vat_amount = db.Column(db.Float, default=0.0)
    net_amount = db.Column(db.Float, default=0.0)

    # Relationship
    payment_voucher = db.relationship('PaymentVoucher', backref='lines', lazy=True)