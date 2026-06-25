from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from models import db, User, Invoice, Expense, Category, AccountType, ChartOfAccount, Supplier, Customer, JournalEntry, \
    Purchase, PaymentVoucher, PaymentVoucherLine
from forms import LoginForm, RegistrationForm, InvoiceForm, ExpenseForm, AccountTypeForm, ChartOfAccountForm, \
    SupplierForm, CustomerForm, PurchaseForm, PaymentVoucherForm
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from io import BytesIO
import os
from werkzeug.utils import secure_filename
import uuid
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///accounting.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuration for file uploads
UPLOAD_FOLDER = 'uploads/journal_attachments'
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Create database tables
with app.app_context():
    db.create_all()
    # Create default categories if none exist
    if Category.query.count() == 0:
        default_categories = ['Sales', 'Services', 'Products', 'Consulting']
        for cat in default_categories:
            category = Category(name=cat)
            db.session.add(category)
        db.session.commit()

    # Create default payment accounts if they don't exist
    asset_type = AccountType.query.filter_by(name='Asset').first()
    liability_type = AccountType.query.filter_by(name='Liability').first()
    expense_type = AccountType.query.filter_by(name='Expense').first()

    if not asset_type:
        asset_type = AccountType(name='Asset', normal_balance='Debit')
        db.session.add(asset_type)

    if not liability_type:
        liability_type = AccountType(name='Liability', normal_balance='Credit')
        db.session.add(liability_type)

    if not expense_type:
        expense_type = AccountType(name='Expense', normal_balance='Debit')
        db.session.add(expense_type)

    db.session.commit()

    # Create Accounts Payable account if not exists
    ap_account = ChartOfAccount.query.filter_by(account_code='2000').first()
    if not ap_account:
        ap_account = ChartOfAccount(
            account_code='2000',
            account_name='Accounts Payable',
            account_type_id=liability_type.id if liability_type else None,
            description='Trade payables to suppliers',
            balance=0.0
        )
        db.session.add(ap_account)

    # Create WHT Payable account if not exists
    wht_account = ChartOfAccount.query.filter_by(account_code='2010').first()
    if not wht_account:
        wht_account = ChartOfAccount(
            account_code='2010',
            account_name='WHT Payable',
            account_type_id=liability_type.id if liability_type else None,
            description='Withholding Tax Payable',
            balance=0.0
        )
        db.session.add(wht_account)

    # Create VAT Receivable account if not exists
    vat_account = ChartOfAccount.query.filter_by(account_code='1105').first()
    if not vat_account:
        vat_account = ChartOfAccount(
            account_code='1105',
            account_name='VAT Receivable',
            account_type_id=asset_type.id if asset_type else None,
            description='Input VAT Receivable',
            balance=0.0
        )
        db.session.add(vat_account)

    db.session.commit()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=hashed_password
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    total_invoices = db.session.query(db.func.sum(Invoice.amount)).filter_by(user_id=current_user.id).scalar() or 0
    total_expenses = db.session.query(db.func.sum(Expense.amount)).filter_by(user_id=current_user.id).scalar() or 0
    net_income = total_invoices - total_expenses

    recent_invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.date.desc()).limit(5).all()
    recent_expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).limit(5).all()

    current_month = datetime.now().month
    current_year = datetime.now().year

    monthly_invoices = db.session.query(db.func.sum(Invoice.amount)).filter(
        Invoice.user_id == current_user.id,
        db.extract('month', Invoice.date) == current_month,
        db.extract('year', Invoice.date) == current_year
    ).scalar() or 0

    monthly_expenses = db.session.query(db.func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        db.extract('month', Expense.date) == current_month,
        db.extract('year', Expense.date) == current_year
    ).scalar() or 0

    return render_template('dashboard.html',
                           total_invoices=total_invoices,
                           total_expenses=total_expenses,
                           net_income=net_income,
                           recent_invoices=recent_invoices,
                           recent_expenses=recent_expenses,
                           monthly_invoices=monthly_invoices,
                           monthly_expenses=monthly_expenses)


@app.route('/invoices')
@login_required
def invoices():
    invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.date.desc()).all()
    return render_template('invoices.html', invoices=invoices)


@app.route('/add_invoice', methods=['GET', 'POST'])
@login_required
def add_invoice():
    form = InvoiceForm()
    categories = Category.query.all()
    form.category.choices = [(c.id, c.name) for c in categories]

    if form.validate_on_submit():
        invoice = Invoice(
            invoice_number=form.invoice_number.data,
            customer_name=form.customer_name.data,
            amount=form.amount.data,
            date=form.date.data,
            status=form.status.data,
            description=form.description.data,
            category_id=form.category.data,
            user_id=current_user.id
        )
        db.session.add(invoice)
        db.session.commit()
        flash('Invoice added successfully!', 'success')
        return redirect(url_for('invoices'))

    return render_template('add_invoice.html', form=form)


@app.route('/view_invoice/<int:id>')
@login_required
def view_invoice(id):
    invoice = Invoice.query.get_or_404(id)
    if invoice.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('invoices'))
    return render_template('view_invoice.html', invoice=invoice)


@app.route('/download_invoice/<int:id>')
@login_required
def download_invoice(id):
    invoice = Invoice.query.get_or_404(id)
    if invoice.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('invoices'))

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        alignment=1
    )

    elements.append(Paragraph(f"Invoice #{invoice.invoice_number}", title_style))
    elements.append(Spacer(1, 20))

    data = [
        ['Customer:', invoice.customer_name],
        ['Date:', invoice.date.strftime('%Y-%m-%d')],
        ['Amount:', f"${invoice.amount:,.2f}"],
        ['Status:', invoice.status],
        ['Description:', invoice.description or 'N/A']
    ]

    table = Table(data, colWidths=[100, 300])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f'invoice_{invoice.invoice_number}.pdf',
                     mimetype='application/pdf')


@app.route('/expenses')
@login_required
def expenses():
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()
    return render_template('expenses.html', expenses=expenses)


@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    form = ExpenseForm()
    categories = Category.query.all()
    form.category.choices = [(c.id, c.name) for c in categories]

    if form.validate_on_submit():
        expense = Expense(
            description=form.description.data,
            amount=form.amount.data,
            date=form.date.data,
            payment_method=form.payment_method.data,
            category_id=form.category.data,
            user_id=current_user.id
        )
        db.session.add(expense)
        db.session.commit()
        flash('Expense added successfully!', 'success')
        return redirect(url_for('expenses'))

    return render_template('add_expense.html', form=form)


@app.route('/chart_of_accounts')
@login_required
def chart_of_accounts():
    accounts = ChartOfAccount.query.filter_by(is_active=True).order_by(ChartOfAccount.account_code).all()
    account_types = AccountType.query.all()
    return render_template('chart_of_accounts.html', accounts=accounts, account_types=account_types)


@app.route('/add_account_type', methods=['GET', 'POST'])
@login_required
def add_account_type():
    form = AccountTypeForm()
    if form.validate_on_submit():
        account_type = AccountType(
            name=form.name.data,
            description=form.description.data,
            normal_balance=form.normal_balance.data
        )
        db.session.add(account_type)
        db.session.commit()
        flash('Account type added successfully!', 'success')
        return redirect(url_for('chart_of_accounts'))
    return render_template('add_account_type.html', form=form)


@app.route('/add_account', methods=['GET', 'POST'])
@login_required
def add_account():
    form = ChartOfAccountForm()
    form.account_type_id.choices = [(t.id, t.name) for t in AccountType.query.all()]

    if form.validate_on_submit():
        account = ChartOfAccount(
            account_code=form.account_code.data,
            account_name=form.account_name.data,
            account_type_id=form.account_type_id.data,
            description=form.description.data,
            balance=form.opening_balance.data
        )
        db.session.add(account)
        db.session.commit()

        if form.opening_balance.data != 0:
            account_type = AccountType.query.get(form.account_type_id.data)
            if account_type:
                journal = JournalEntry(
                    entry_number=f"OPEN-{account.account_code}",
                    date=datetime.now().date(),
                    description=f"Opening balance for {account.account_name}",
                    account_id=account.id,
                    debit=form.opening_balance.data if account_type.normal_balance == 'Debit' else 0,
                    credit=form.opening_balance.data if account_type.normal_balance == 'Credit' else 0,
                    reference_type='Opening Balance',
                    user_id=current_user.id
                )
                db.session.add(journal)
                db.session.commit()

        flash('Account added successfully!', 'success')
        return redirect(url_for('chart_of_accounts'))

    return render_template('add_account.html', form=form)


@app.route('/suppliers')
@login_required
def suppliers():
    suppliers_list = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    return render_template('suppliers.html', suppliers=suppliers_list)


@app.route('/add_supplier', methods=['GET', 'POST'])
@login_required
def add_supplier():
    form = SupplierForm()
    if form.validate_on_submit():
        supplier = Supplier(
            supplier_code=form.supplier_code.data,
            name=form.name.data,
            contact_person=form.contact_person.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            tax_id=form.tax_id.data,
            payment_terms=form.payment_terms.data,
            opening_balance=form.opening_balance.data,
            current_balance=form.opening_balance.data
        )
        db.session.add(supplier)
        db.session.commit()
        flash('Supplier added successfully!', 'success')
        return redirect(url_for('suppliers'))
    return render_template('add_supplier.html', form=form)


@app.route('/view_supplier/<int:id>')
@login_required
def view_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    purchases = Purchase.query.filter_by(supplier_id=id).order_by(Purchase.date.desc()).all()
    return render_template('view_supplier.html', supplier=supplier, purchases=purchases)


@app.route('/customers')
@login_required
def customers():
    customers_list = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    return render_template('customers.html', customers=customers_list)


@app.route('/add_customer', methods=['GET', 'POST'])
@login_required
def add_customer():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer(
            customer_code=form.customer_code.data,
            name=form.name.data,
            contact_person=form.contact_person.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            tax_id=form.tax_id.data,
            credit_limit=form.credit_limit.data,
            opening_balance=form.opening_balance.data,
            current_balance=form.opening_balance.data,
            payment_terms=form.payment_terms.data
        )
        db.session.add(customer)
        db.session.commit()
        flash('Customer added successfully!', 'success')
        return redirect(url_for('customers'))
    return render_template('add_customer.html', form=form)


@app.route('/view_customer/<int:id>')
@login_required
def view_customer(id):
    customer = Customer.query.get_or_404(id)
    invoices = Invoice.query.filter_by(customer_name=customer.name).order_by(Invoice.date.desc()).all()
    return render_template('view_customer.html', customer=customer, invoices=invoices)


@app.route('/purchases')
@login_required
def purchases():
    purchases_list = Purchase.query.filter_by(user_id=current_user.id).order_by(Purchase.date.desc()).all()
    return render_template('purchases.html', purchases=purchases_list)


@app.route('/add_purchase', methods=['GET', 'POST'])
@login_required
def add_purchase():
    form = PurchaseForm()
    form.supplier_id.choices = [(0, 'Select Supplier')] + [(s.id, s.name) for s in
                                                           Supplier.query.filter_by(is_active=True).all()]
    form.category_id.choices = [(0, 'Select Category')] + [(c.id, c.name) for c in Category.query.all()]

    if form.validate_on_submit():
        purchase = Purchase(
            purchase_number=form.purchase_number.data,
            supplier_id=form.supplier_id.data,
            invoice_number=form.invoice_number.data,
            amount=form.amount.data,
            date=form.date.data,
            due_date=form.due_date.data,
            status=form.status.data,
            description=form.description.data,
            category_id=form.category_id.data if form.category_id.data != 0 else None,
            user_id=current_user.id
        )
        db.session.add(purchase)

        supplier = Supplier.query.get(form.supplier_id.data)
        if supplier:
            supplier.current_balance += form.amount.data

        db.session.commit()
        flash('Purchase added successfully!', 'success')
        return redirect(url_for('purchases'))

    return render_template('add_purchase.html', form=form)


@app.route('/trial_balance')
@login_required
def trial_balance():
    accounts = ChartOfAccount.query.filter_by(is_active=True).all()
    trial_balance_data = []
    total_debits = 0
    total_credits = 0

    for account in accounts:
        debits = db.session.query(db.func.sum(JournalEntry.debit)).filter_by(account_id=account.id).scalar() or 0
        credits = db.session.query(db.func.sum(JournalEntry.credit)).filter_by(account_id=account.id).scalar() or 0
        balance = debits - credits

        account_type = AccountType.query.get(account.account_type_id)
        if account_type:
            if account_type.normal_balance == 'Debit':
                if balance > 0:
                    total_debits += balance
                    debit_amount = balance
                    credit_amount = 0
                else:
                    total_credits += abs(balance)
                    debit_amount = 0
                    credit_amount = abs(balance)
            else:
                if balance > 0:
                    total_credits += balance
                    debit_amount = 0
                    credit_amount = balance
                else:
                    total_debits += abs(balance)
                    debit_amount = abs(balance)
                    credit_amount = 0
        else:
            debit_amount = 0
            credit_amount = 0

        trial_balance_data.append({
            'account_code': account.account_code,
            'account_name': account.account_name,
            'account_type': account_type.name if account_type else 'N/A',
            'debit': debit_amount,
            'credit': credit_amount
        })

    return render_template('trial_balance.html',
                           trial_balance=trial_balance_data,
                           total_debits=total_debits,
                           total_credits=total_credits,
                           datetime=datetime)


@app.route('/journal_entries')
@login_required
def journal_entries():
    entries = JournalEntry.query.filter_by(user_id=current_user.id).order_by(JournalEntry.date.desc(),
                                                                             JournalEntry.entry_number.desc()).all()
    grouped_entries = {}
    for entry in entries:
        if entry.entry_number not in grouped_entries:
            grouped_entries[entry.entry_number] = []
        grouped_entries[entry.entry_number].append(entry)
    return render_template('journal_entries.html', grouped_entries=grouped_entries)


@app.route('/add_journal_entry', methods=['GET', 'POST'])
@login_required
def add_journal_entry():
    from datetime import datetime as dt

    accounts = ChartOfAccount.query.filter_by(is_active=True).order_by(ChartOfAccount.account_code).all()
    accounts_serializable = [{'id': a.id, 'account_code': a.account_code, 'account_name': a.account_name} for a in
                             accounts]

    if request.method == 'POST':
        try:
            entry_count = int(request.form.get('entry_count', 1))
            entries_data = []
            total_amount = 0

            for i in range(entry_count):
                date = request.form.get(f'entries-{i}-date')
                description = request.form.get(f'entries-{i}-description')
                debit_account_id = request.form.get(f'entries-{i}-debit_account')
                credit_account_id = request.form.get(f'entries-{i}-credit_account')
                amount = float(request.form.get(f'entries-{i}-amount', 0) or 0)

                if debit_account_id and credit_account_id and amount > 0:
                    entries_data.append({
                        'date': date,
                        'description': description,
                        'debit_account_id': int(debit_account_id),
                        'credit_account_id': int(credit_account_id),
                        'amount': amount,
                        'index': i
                    })
                    total_amount += amount

            if total_amount == 0:
                flash('At least one entry must have an amount greater than 0', 'danger')
                return render_template('add_journal_entry.html', accounts=accounts, accounts_json=accounts_serializable,
                                       entry_count=entry_count, datetime=dt)

            for entry_data in entries_data:
                attachment_filename = None
                attachment_original_name = None
                file_field = f'entries-{entry_data["index"]}-attachment'
                if file_field in request.files:
                    file = request.files[file_field]
                    if file and file.filename and allowed_file(file.filename):
                        original_filename = secure_filename(file.filename)
                        attachment_filename = f"{uuid.uuid4().hex}_{original_filename}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], attachment_filename)
                        file.save(file_path)
                        attachment_original_name = original_filename

                debit_journal = JournalEntry(
                    date=dt.strptime(entry_data['date'], '%Y-%m-%d').date(),
                    description=entry_data['description'],
                    account_id=entry_data['debit_account_id'],
                    debit=entry_data['amount'],
                    credit=0,
                    attachment_filename=attachment_filename,
                    attachment_original_name=attachment_original_name,
                    reference_type='Manual Entry',
                    user_id=current_user.id
                )

                credit_journal = JournalEntry(
                    date=dt.strptime(entry_data['date'], '%Y-%m-%d').date(),
                    description=entry_data['description'],
                    account_id=entry_data['credit_account_id'],
                    debit=0,
                    credit=entry_data['amount'],
                    attachment_filename=attachment_filename,
                    attachment_original_name=attachment_original_name,
                    reference_type='Manual Entry',
                    user_id=current_user.id
                )

                debit_account = db.session.get(ChartOfAccount, entry_data['debit_account_id'])
                credit_account = db.session.get(ChartOfAccount, entry_data['credit_account_id'])

                if debit_account:
                    debit_account.balance += entry_data['amount']
                if credit_account:
                    credit_account.balance -= entry_data['amount']

                db.session.add(debit_journal)
                db.session.add(credit_journal)

            db.session.commit()
            flash(f'Journal entry created successfully with {len(entries_data)} transaction(s)!', 'success')
            return redirect(url_for('journal_entries'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating journal entry: {str(e)}', 'danger')
            return render_template('add_journal_entry.html', accounts=accounts, accounts_json=accounts_serializable,
                                   entry_count=entry_count, datetime=dt)

    return render_template('add_journal_entry.html', accounts=accounts, accounts_json=accounts_serializable,
                           entry_count=1, datetime=datetime)


@app.route('/view_journal_entry/<entry_number>')
@login_required
def view_journal_entry(entry_number):
    entries = JournalEntry.query.filter_by(entry_number=entry_number, user_id=current_user.id).order_by(
        JournalEntry.id).all()
    if not entries:
        flash('Journal entry not found', 'danger')
        return redirect(url_for('journal_entries'))

    total_debits = sum(e.debit for e in entries)
    total_credits = sum(e.credit for e in entries)

    return render_template('view_journal_entry.html', entries=entries, entry_number=entry_number,
                           total_debits=total_debits, total_credits=total_credits)


@app.route('/download_attachment/<int:entry_id>')
@login_required
def download_attachment(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    if entry.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('journal_entries'))

    if entry.attachment_filename:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], entry.attachment_filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=entry.attachment_original_name)
        else:
            flash('File not found', 'danger')
    else:
        flash('No attachment found', 'warning')

    return redirect(url_for('journal_entries'))


@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')


# Payment Voucher Routes
@app.route('/payment_vouchers')
@login_required
def payment_vouchers():
    vouchers = PaymentVoucher.query.filter_by(user_id=current_user.id).order_by(PaymentVoucher.date.desc()).all()
    return render_template('payment_vouchers.html', vouchers=vouchers)


@app.route('/add_payment_voucher', methods=['GET', 'POST'])
@login_required
def add_payment_voucher():
    from datetime import datetime as dt

    form = PaymentVoucherForm()

    suppliers = Supplier.query.filter_by(is_active=True).all()
    form.supplier_id.choices = [(0, 'Select Supplier')] + [(s.id, s.name) for s in suppliers]

    accounts = ChartOfAccount.query.filter_by(is_active=True).order_by(ChartOfAccount.account_code).all()
    form.debit_account_id.choices = [(0, 'Select Debit Account')] + [(a.id, f"{a.account_code} - {a.account_name}") for
                                                                     a in accounts]

    if request.method == 'POST':
        try:
            entry_count = int(request.form.get('entry_count', 1))
            lines = []
            total_gross = 0
            total_wht = 0
            total_vat = 0
            total_net = 0

            # Collect all line items from the form
            for i in range(entry_count):
                description = request.form.get(f'entries-{i}-description', '').strip()
                wht_rate = float(request.form.get(f'entries-{i}-wht_rate', 0) or 0)
                vat_rate = float(request.form.get(f'entries-{i}-vat_rate', 0) or 0)
                gross_amount = float(request.form.get(f'entries-{i}-gross_amount', 0) or 0)

                if gross_amount > 0:
                    wht_amount = gross_amount * (wht_rate / 100)
                    vat_amount = gross_amount * (vat_rate / 100)
                    net_amount = gross_amount - wht_amount + vat_amount

                    lines.append({
                        'description': description if description else f"Item {i + 1}",
                        'wht_rate': wht_rate,
                        'vat_rate': vat_rate,
                        'gross_amount': gross_amount,
                        'wht_amount': wht_amount,
                        'vat_amount': vat_amount,
                        'net_amount': net_amount
                    })

                    total_gross += gross_amount
                    total_wht += wht_amount
                    total_vat += vat_amount
                    total_net += net_amount

            if total_gross == 0:
                flash('At least one entry with a gross amount is required', 'danger')
                return render_template('add_payment_voucher.html', form=form)

            # Generate voucher number
            voucher_number = f"PV-{dt.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

            # Handle file attachment
            attachment_filename = None
            attachment_original_name = None
            if form.attachment.data:
                file = form.attachment.data
                if file and allowed_file(file.filename):
                    original_filename = secure_filename(file.filename)
                    attachment_filename = f"{uuid.uuid4().hex}_{original_filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], attachment_filename)
                    file.save(file_path)
                    attachment_original_name = original_filename

            # Create the main voucher
            voucher = PaymentVoucher(
                voucher_number=voucher_number,
                supplier_id=form.supplier_id.data,
                currency=form.currency.data,
                exchange_rate=form.exchange_rate.data,
                date=form.date.data,
                debit_account_id=form.debit_account_id.data,
                gross_amount=total_gross,
                wht_amount=total_wht,
                vat_amount=total_vat,
                net_amount=total_net,
                reference_number=form.reference_number.data,
                attachment_filename=attachment_filename,
                attachment_original_name=attachment_original_name,
                user_id=current_user.id
            )

            db.session.add(voucher)
            db.session.flush()  # This assigns the voucher.id

            # Save each line item - CRITICAL: Use the voucher.id
            for line in lines:
                voucher_line = PaymentVoucherLine(
                    payment_voucher_id=voucher.id,
                    description=line['description'],
                    wht_rate=line['wht_rate'],
                    vat_rate=line['vat_rate'],
                    gross_amount=line['gross_amount'],
                    wht_amount=line['wht_amount'],
                    vat_amount=line['vat_amount'],
                    net_amount=line['net_amount']
                )
                db.session.add(voucher_line)

            # Commit everything
            db.session.commit()

            flash(f'Payment Voucher {voucher_number} created successfully with {len(lines)} item(s)!', 'success')
            return redirect(url_for('payment_vouchers'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating payment voucher: {str(e)}', 'danger')
            return render_template('add_payment_voucher.html', form=form)

    return render_template('add_payment_voucher.html', form=form)

@app.route('/view_payment_voucher/<int:id>')
@login_required
def view_payment_voucher(id):
    voucher = PaymentVoucher.query.get_or_404(id)
    if voucher.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('payment_vouchers'))
    return render_template('view_payment_voucher.html', voucher=voucher)


@app.route('/download_voucher_attachment/<int:id>')
@login_required
def download_voucher_attachment(id):
    voucher = PaymentVoucher.query.get_or_404(id)
    if voucher.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('payment_vouchers'))

    if voucher.attachment_filename:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], voucher.attachment_filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=voucher.attachment_original_name)
        else:
            flash('File not found', 'danger')
    else:
        flash('No attachment found', 'warning')

    return redirect(url_for('payment_vouchers'))


@app.route('/print_payment_voucher/<int:id>')
@login_required
def print_payment_voucher(id):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from io import BytesIO

    voucher = PaymentVoucher.query.get_or_404(id)
    if voucher.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('payment_vouchers'))

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=15 * mm,
                            rightMargin=15 * mm)
    elements = []

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16,
                                 textColor=colors.HexColor('#2c3e50'), alignment=1, spaceAfter=20)
    section_style = ParagraphStyle('Section', parent=styles['Heading2'], fontSize=12,
                                   textColor=colors.HexColor('#34495e'), alignment=0, spaceAfter=10, spaceBefore=15)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=9, spaceAfter=4)
    label_style = ParagraphStyle('Label', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', spaceAfter=4)

    elements.append(Paragraph("PAYMENT VOUCHER", title_style))
    elements.append(Spacer(1, 5))

    header_data = [
        [Paragraph("<b>Voucher No:</b>", label_style), voucher.voucher_number, Paragraph("<b>Date:</b>", label_style),
         voucher.date.strftime('%d-%m-%Y')],
        [Paragraph("<b>Reference:</b>", label_style), voucher.reference_number or 'N/A',
         Paragraph("<b>Status:</b>", label_style), voucher.status],
    ]
    header_table = Table(header_data, colWidths=[35 * mm, 55 * mm, 30 * mm, 50 * mm])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 15))

    info_data = [
        [Paragraph("<b>SUPPLIER INFORMATION</b>", label_style), Paragraph("<b>ACCOUNT INFORMATION</b>", label_style)],
        [f"Name: {voucher.supplier.name}",
         f"Debit Account: {voucher.debit_account.account_code} - {voucher.debit_account.account_name}"],
        [f"Email: {voucher.supplier.email or 'N/A'}", f"Credit Account: Accounts Payable - Trade"],
        [f"Phone: {voucher.supplier.phone or 'N/A'}", f"Currency: {voucher.currency} (Rate: {voucher.exchange_rate})"],
    ]
    info_table = Table(info_data, colWidths=[85 * mm, 85 * mm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9), ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6), ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))

    elements.append(Paragraph("PAYMENT LINE ITEMS", section_style))

    line_data = [['#', 'Description', 'WHT %', 'VAT %', 'Gross', 'WHT', 'VAT', 'Net']]
    for idx, line in enumerate(voucher.lines, 1):
        line_data.append([
            str(idx),
            line.description[:40] + '...' if len(line.description) > 40 else line.description,
            f"{line.wht_rate:.2f}%",
            f"{line.vat_rate:.2f}%",
            f"{voucher.currency} {line.gross_amount:,.2f}",
            f"({voucher.currency} {line.wht_amount:,.2f})",
            f"{voucher.currency} {line.vat_amount:,.2f}",
            f"{voucher.currency} {line.net_amount:,.2f}"
        ])

    line_data.append([
        '', Paragraph("<b>TOTAL</b>", normal_style), '', '',
        Paragraph(f"<b>{voucher.currency} {voucher.gross_amount:,.2f}</b>", normal_style),
        Paragraph(f"<b>({voucher.currency} {voucher.wht_amount:,.2f})</b>", normal_style),
        Paragraph(f"<b>{voucher.currency} {voucher.vat_amount:,.2f}</b>", normal_style),
        Paragraph(f"<b>{voucher.currency} {voucher.net_amount:,.2f}</b>", normal_style)
    ])

    line_table = Table(line_data, colWidths=[10 * mm, 55 * mm, 15 * mm, 15 * mm, 25 * mm, 25 * mm, 25 * mm, 25 * mm])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'), ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8), ('ALIGN', (2, 1), (7, -2), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, len(line_data) - 1), (-1, len(line_data) - 1), colors.HexColor('#e8f4f8')),
        ('FONTNAME', (0, len(line_data) - 1), (-1, len(line_data) - 1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(line_table)
    elements.append(Spacer(1, 10))

    summary_data = [
        ['Total Gross Amount:', f"{voucher.currency} {voucher.gross_amount:,.2f}"],
        ['Less: WHT Amount:', f"({voucher.currency} {voucher.wht_amount:,.2f})"],
        ['Add: VAT Amount:', f"{voucher.currency} {voucher.vat_amount:,.2f}"],
        ['NET PAYMENT AMOUNT:', f"{voucher.currency} {voucher.net_amount:,.2f}"]
    ]
    summary_table = Table(summary_data, colWidths=[100 * mm, 70 * mm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'), ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'), ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#e8f4f8')),
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'), ('TEXTCOLOR', (0, 3), (-1, 3), colors.HexColor('#2c3e50')),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 15))

    def number_to_words(amount):
        return f"{amount:,.2f} only"

    elements.append(Paragraph(f"Amount in Words: {number_to_words(voucher.net_amount)}", normal_style))
    elements.append(Spacer(1, 15))

    elements.append(Paragraph("APPROVALS", section_style))

    approval_data = [
        ['', '', '', ''],
        ['PREPARED BY', 'CHECKED BY', 'APPROVED BY', 'RECEIVED BY'],
        ['', '', '', ''],
        ['Name: _______________', 'Name: _______________', 'Name: _______________', 'Name: _______________'],
        ['Signature: __________', 'Signature: __________', 'Signature: __________', 'Signature: __________'],
        ['Date: _______________', 'Date: _______________', 'Date: _______________', 'Date: _______________'],
    ]

    approval_table = Table(approval_data, colWidths=[42.5 * mm, 42.5 * mm, 42.5 * mm, 42.5 * mm])
    approval_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#2c3e50')), ('TEXTCOLOR', (0, 1), (-1, 1), colors.white),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'), ('FONTSIZE', (0, 1), (-1, 1), 10),
        ('ALIGN', (0, 1), (-1, 1), 'CENTER'), ('FONTSIZE', (0, 3), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(approval_table)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("This is a computer-generated document.",
                              ParagraphStyle('Footer', parent=normal_style, textColor=colors.grey, alignment=1,
                                             fontSize=8)))

    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f'payment_voucher_{voucher.voucher_number}.pdf',
                     mimetype='application/pdf')


@app.route('/api/financial_data')
@login_required
def financial_data():
    report_type = request.args.get('type', 'monthly')
    year = request.args.get('year', datetime.now().year)

    if report_type == 'monthly':
        monthly_data = []
        for month in range(1, 13):
            invoice_total = db.session.query(db.func.sum(Invoice.amount)).filter(
                Invoice.user_id == current_user.id,
                db.extract('month', Invoice.date) == month,
                db.extract('year', Invoice.date) == year
            ).scalar() or 0

            expense_total = db.session.query(db.func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                db.extract('month', Expense.date) == month,
                db.extract('year', Expense.date) == year
            ).scalar() or 0

            monthly_data.append({
                'month': datetime(year, month, 1).strftime('%B'),
                'invoices': float(invoice_total),
                'expenses': float(expense_total),
                'profit': float(invoice_total - expense_total)
            })

        return jsonify(monthly_data)

    return jsonify({'error': 'Invalid report type'}), 400


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))