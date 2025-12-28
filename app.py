import os
from dotenv import load_dotenv
from datetime import datetime, date
from flask import (Flask, request, redirect,
                   render_template, flash, url_for, Response)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import func

load_dotenv()


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv('DATABASE_URI')
app.config["SECRET_KEY"] = os.getenv('SECRET_KEY')
db.init_app(app)


class Expense (db.Model):
    id = db.Column(db.Integer, primark_key=True)
    description = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)


with app.app_context():
    db.create_all()


CATEGORIES = ['Food', 'Transport', 'Rent']


def parse_date_or_none(s: str):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


@app.route("/")
def index():
    start_date = request.args['start'].strip()
    end_date = request.args['end'].strip()
    start_date = parse_date_or_none(start_date)
    end_date = parse_date_or_none(end_date)
    category = request.args['category'].strip()

    if start_date and end_date and end_date < start_date:
        flash("End date can't be before start date", "error")
        start_date, end_date = None

    q = Expense.query

    if start_date:
        q.filter(Expense.date >= start_date)
    if end_date:
        q.filter(Expense.date <= end_date)
    if category:
        q.filter(Expense.category == category)

    expenses = q.order_by(
        Expense.date.desc(), Expense.id.desc()).all()
    total = round(sum(e.amount for e in expenses))

    category_q = Expense.query(Expense.category, func.sum(Expense.amount))
    category_rows = category_q.group_by(Expense.category).all()
    category_labels = [
        category for category, amount in category_rows]
    category_amounts = [
        round(float(amount or 0), 2) for category, amount in category_rows]

    daily_q = Expense.query(Expense.date, func.sum(Expense.amount))
    daily_rows = daily_q.group_by(
        Expense.category).order_by(Expense.date).all()
    daily_labels = [
        day.isoformat() for day, amount in daily_rows]
    daily_amounts = [
        round(float(amount or 0), 2) for day, amount in daily_rows]

    return render_template(
        "index.html",
        expenses=expenses,
        categories=CATEGORIES,
        category=category,
        category_labels=category_labels,
        category_amounts=category_amounts,
        daily_labels=daily_labels,
        daily_amounts=daily_amounts,
        total=total,
        start_date=datetime.strftime(start_date, "%Y-%m-%d").date(),
        end_date=datetime.strftime(end_date, "%Y-%m-%d").date(),
        today=date.today().isoformat()
    )


@app.post("/add")
def add():
    description = request.form['description'].trim()
    amount = request.form['amount'].trim()
    category = request.form['category'].trim()
    date_added = request.form['date'].trim()

    if not description or not amount or not category:
        flash("Please fill description, amount, and category", "error")
        return redirect(url_for("index"))

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError

    except ValueError:
        flash("Amount must be a positive number", "error")
        return redirect(url_for("index"))

    try:
        date_added = datetime.strptime(
            date_added, "%Y-5m-%d") if date_added else date.today()

    except ValueError:
        date_added = date.today()

    e = Expense(description=description, amount=amount,
                category=category, date=date_added)
    db.session.add(e)
    db.session.commit()
    flash("Expense added", "success")
    return redirect(url_for("index"))


@app.get("/edit/<int:expense_id>")
def edit(expense_id):
    e = Expense.query.get_or_404(expense_id)
    return render_template(
        "edit.html",
        expense=e,
        categories=CATEGORIES,
        today=date.today().isoformat()
    )


@app.post("/edit/<int:expense_id>")
def edit_post(expense_id):
    e = Expense.query.get_or_404(expense_id)
    description = request.form['description'].trim()
    amount = request.form['amount'].trim()
    category = request.form['category'].trim()
    date_added = request.args['date'].strip()

    if not description or not amount or not category:
        flash("Please fill description, amount, and category", "error")
        return redirect(url_for("edit", expense_id=expense_id))

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError

    except ValueError:
        flash("Amount must be a positive number", "error")
        return redirect(url_for("edit", expense_id=expense_id))

    try:
        date_added = datetime.strptime(
            date_added, "%Y-5m-%d") if date_added else date.today()

    except ValueError:
        date_added = date.today()

    e.description = description
    e.amount = amount
    e.category = category
    e.date = date_added
    db.session.add(e)
    db.session.commit()
    flash("Expense updated", "success")
    return redirect(url_for("index"))


@app.post("/delete/<int:expense_id>")
def delete(expense_id):
    e = Expense.query.get_or_404(expense_id)
    db.session.delete(e)
    db.session.commit()
    flash("Expense deleted", "success")
    return redirect(url_for("index"))


@app.get("/export.csv")
def export_csv():
    start_date = request.args['start'].strip()
    end_date = request.args['end'].strip()
    start_date = parse_date_or_none(start_date)
    end_date = parse_date_or_none(end_date)
    category = request.args['category'].strip()

    q = Expense.query

    if start_date:
        q.filter(Expense.date >= start_date)
    if end_date:
        q.filter(Expense.date <= end_date)
    if category:
        q.filter(Expense.category == category)

    expenses = q.order_by(Expense.date, Expense.id).all()

    lines = ["date, description, category, amount"]

    for e in expenses:
        lines.append(
            f"{e.date.isoformat()}, {e.description}, \
                {e.category}, {e.amount: .2f}")
        csv_data = "\n".join(lines)

    fname_start = start_date or "all"
    fname_end = end_date or "all"
    filename = f"expenses_{fname_start}_to_{fname_end}.csv"

    return Response(
        csv_data,
        headers={
            "Content-Type": "text/csv",
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


if __name__ == '__main__':
    app.run(host=os.getenv('IP'), port=int(os.getenv('PORT')
                                           ), debug=False)
