from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FloatField, DateField, SelectField, TextAreaField, BooleanField
from wtforms.validators import DataRequired, EqualTo, Length, ValidationError
from models import User, ChartOfAccount, Supplier, Customer
from datetime import datetime
from wtforms import FieldList, FormField
from flask_wtf.file import FileField, FileAllowed, FileRequired

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


class InvoiceForm(FlaskForm):
    invoice_number = StringField('Invoice Number', validators=[DataRequired()])
    customer_name = StringField('Customer Name', validators=[DataRequired()])
    amount = FloatField('Amount', validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()], default=datetime.today)
    status = SelectField('Status', choices=[('Paid', 'Paid'), ('Pending', 'Pending'), ('Overdue', 'Overdue')])
    description = TextAreaField('Description')
    category = SelectField('Category', choices=[], coerce=int)
    submit = SubmitField('Add Invoice')


class ExpenseForm(FlaskForm):
    description = StringField('Description', validators=[DataRequired()])
    amount = FloatField('Amount', validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()], default=datetime.today)
    payment_method = SelectField('Payment Method', choices=[('Cash', 'Cash'), ('Credit Card', 'Credit Card'),
                                                            ('Bank Transfer', 'Bank Transfer')])
    category = SelectField('Category', choices=[], coerce=int)
    submit = SubmitField('Add Expense')


class AccountTypeForm(FlaskForm):
    name = StringField('Account Type Name', validators=[DataRequired(), Length(max=50)])
    description = TextAreaField('Description')
    normal_balance = SelectField('Normal Balance', choices=[('Debit', 'Debit'), ('Credit', 'Credit')])
    submit = SubmitField('Add Account Type')


class ChartOfAccountForm(FlaskForm):
    account_code = StringField('Account Code', validators=[DataRequired(), Length(max=20)])
    account_name = StringField('Account Name', validators=[DataRequired(), Length(max=100)])
    account_type_id = SelectField('Account Type', choices=[], coerce=int)
    description = TextAreaField('Description')
    opening_balance = FloatField('Opening Balance', default=0.0)
    submit = SubmitField('Add Account')

    def validate_account_code(self, account_code):
        account = ChartOfAccount.query.filter_by(account_code=account_code.data).first()
        if account:
            raise ValidationError('Account code already exists.')


class SupplierForm(FlaskForm):
    supplier_code = StringField('Supplier Code', validators=[DataRequired(), Length(max=20)])
    name = StringField('Company Name', validators=[DataRequired(), Length(max=100)])
    contact_person = StringField('Contact Person', validators=[Length(max=100)])
    email = StringField('Email', validators=[DataRequired()])
    phone = StringField('Phone', validators=[Length(max=20)])
    address = TextAreaField('Address')
    tax_id = StringField('Tax ID/VAT Number', validators=[Length(max=50)])
    payment_terms = SelectField('Payment Terms', choices=[
        ('Net 15', 'Net 15'),
        ('Net 30', 'Net 30'),
        ('Net 45', 'Net 45'),
        ('Net 60', 'Net 60'),
        ('Cash on Delivery', 'Cash on Delivery')
    ])
    opening_balance = FloatField('Opening Balance', default=0.0)
    submit = SubmitField('Add Supplier')

    def validate_supplier_code(self, supplier_code):
        supplier = Supplier.query.filter_by(supplier_code=supplier_code.data).first()
        if supplier:
            raise ValidationError('Supplier code already exists.')


class CustomerForm(FlaskForm):
    customer_code = StringField('Customer Code', validators=[DataRequired(), Length(max=20)])
    name = StringField('Company/Person Name', validators=[DataRequired(), Length(max=100)])
    contact_person = StringField('Contact Person', validators=[Length(max=100)])
    email = StringField('Email', validators=[DataRequired()])
    phone = StringField('Phone', validators=[Length(max=20)])
    address = TextAreaField('Address')
    tax_id = StringField('Tax ID/VAT Number', validators=[Length(max=50)])
    credit_limit = FloatField('Credit Limit', default=0.0)
    opening_balance = FloatField('Opening Balance', default=0.0)
    payment_terms = SelectField('Payment Terms', choices=[
        ('Net 15', 'Net 15'),
        ('Net 30', 'Net 30'),
        ('Net 45', 'Net 45'),
        ('Net 60', 'Net 60'),
        ('Due on Receipt', 'Due on Receipt')
    ])
    submit = SubmitField('Add Customer')

    def validate_customer_code(self, customer_code):
        customer = Customer.query.filter_by(customer_code=customer_code.data).first()
        if customer:
            raise ValidationError('Customer code already exists.')


class PurchaseForm(FlaskForm):
    purchase_number = StringField('Purchase Order #', validators=[DataRequired()])
    supplier_id = SelectField('Supplier', choices=[], coerce=int)
    invoice_number = StringField('Supplier Invoice #')
    amount = FloatField('Amount', validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()], default=datetime.today)
    due_date = DateField('Due Date')
    status = SelectField('Status', choices=[
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Overdue', 'Overdue')
    ])
    description = TextAreaField('Description')
    category_id = SelectField('Category', choices=[], coerce=int)
    submit = SubmitField('Add Purchase')

    def validate_amount(self, amount):
        if amount.data <= 0:
            raise ValidationError('Amount must be greater than 0')

    class JournalEntryForm(FlaskForm):
        entry_number = StringField('Journal Entry #', validators=[DataRequired()])
        date = DateField('Date', validators=[DataRequired()], default=datetime.today)
        description = TextAreaField('Description', validators=[DataRequired()])
        account_id = SelectField('Account', choices=[], coerce=int)
        debit = FloatField('Debit Amount', default=0.0)
        credit = FloatField('Credit Amount', default=0.0)
        submit = SubmitField('Add Journal Entry')

        def validate_debit_credit(self):
            if self.debit.data > 0 and self.credit.data > 0:
                raise ValidationError('Cannot have both debit and credit amounts')
            if self.debit.data == 0 and self.credit.data == 0:
                raise ValidationError('Either debit or credit amount must be greater than 0')
            return True


class JournalEntryForm(FlaskForm):
    entry_number = StringField('Journal Entry #', validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()], default=datetime.today)
    description = TextAreaField('Description', validators=[DataRequired()])
    account_id = SelectField('Account', choices=[], coerce=int)
    debit = FloatField('Debit Amount', default=0.0)
    credit = FloatField('Credit Amount', default=0.0)
    submit = SubmitField('Add Journal Entry')

    def validate_debit_credit(self):
        if self.debit.data > 0 and self.credit.data > 0:
            raise ValidationError('Cannot have both debit and credit amounts')
        if self.debit.data == 0 and self.credit.data == 0:
            raise ValidationError('Either debit or credit amount must be greater than 0')
        return True


class JournalLineForm(FlaskForm):
    account_id = SelectField('Account', choices=[], coerce=int)
    debit = FloatField('Debit', default=0.0)
    credit = FloatField('Credit', default=0.0)


class MultiJournalEntryForm(FlaskForm):
    entry_number = StringField('Journal Entry #', validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()], default=datetime.today)
    description = TextAreaField('Description', validators=[DataRequired()])
    lines = FieldList(FormField(JournalLineForm), min_entries=2, max_entries=10)
    submit = SubmitField('Save Journal Entry')


class JournalEntryFormNew(FlaskForm):
    date = DateField('Date', validators=[DataRequired()], default=datetime.today)
    account_id = SelectField('Account Name', choices=[], coerce=int, validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    debit = FloatField('Debit', default=0.0)
    credit = FloatField('Credit', default=0.0)
    attachment = FileField('Attach File',
                           validators=[FileAllowed(['pdf', 'jpg', 'png', 'doc', 'docx'], 'PDF, JPG, PNG, DOC only!')])
    submit = SubmitField('Save Entry')

    def validate_debit_credit(self):
        if self.debit.data > 0 and self.credit.data > 0:
            raise ValidationError('Cannot have both debit and credit amounts')
        if self.debit.data == 0 and self.credit.data == 0:
            raise ValidationError('Either debit or credit amount must be greater than 0')
        return True

class HorizontalJournalEntryForm(FlaskForm):
    entries = FieldList(FormField(JournalLineForm), min_entries=1, max_entries=20)
    submit = SubmitField('Save All Entries')


class PaymentVoucherForm(FlaskForm):
    voucher_number = StringField('Voucher #', validators=[DataRequired()])
    supplier_id = SelectField('Supplier', choices=[], coerce=int, validators=[DataRequired()])
    currency = SelectField('Currency', choices=[
        ('USD', 'USD - US Dollar'),
        ('EUR', 'EUR - Euro'),
        ('GBP', 'GBP - British Pound'),
        ('GHS', 'GHS - Ghana Cedi'),
        ('NGN', 'NGN - Nigerian Naira')
    ], default='USD')
    exchange_rate = FloatField('Exchange Rate', default=1.0, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()], default=datetime.today)
    description = TextAreaField('Description', validators=[DataRequired()])
    debit_account_id = SelectField('Debit Account', choices=[], coerce=int, validators=[DataRequired()])
    wht_rate = FloatField('WHT Rate (%)', default=0.0)
    vat_rate = FloatField('VAT Rate (%)', default=0.0)
    gross_amount = FloatField('Gross Amount', validators=[DataRequired()])
    reference_number = StringField('Reference #')
    attachment = FileField('Support Document', validators=[
        FileAllowed(['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'], 'PDF, JPG, PNG, DOC only!')])
    submit = SubmitField('Save Payment Voucher')

    def validate_gross_amount(self, gross_amount):
        if gross_amount.data <= 0:
            raise ValidationError('Gross amount must be greater than 0')