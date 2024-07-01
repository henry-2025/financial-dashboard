import argparse, os, sqlite3
from typing import IO, Optional, Set
from flask import Flask, render_template, redirect, request, session
import pandas as pd
import numpy as np
from transaction_parsers import parse_transaction
from werkzeug.datastructures import FileStorage

app = Flask(__name__)
app.secret_key = 'db2c0d8a-275c-11ef-b5da-e32f975dcd51'

@app.route("/")
def start_page():
    #TODO: implement startup business logic
    session.clear()
    return render_template("start.html")

def init_db() -> sqlite3.Connection:
    db = sqlite3.connect('history.db')
    with open('schema.sql', 'r') as schema:
        script = ''.join(schema.readlines())
        db.executescript(script)
    return db

def db_connect() -> sqlite3.Connection:
    return sqlite3.connect('history.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)



def load_history() -> Optional[list]:
    db = init_db()
    try:
        history = db.execute('''SELECT
                                    l.description,
                                    l.amount,
                                    t.description AS type
                                FROM transaction_labels l
                                LEFT JOIN transaction_types t
                                ON l.type = t.type''').fetchall()
    except:
        return None

def table_diff(history: list, current_tables: pd.DataFrame) -> Set:
    history_ids = set(map(lambda x: x['id'], history))
    return current_tables.index - history_ids

def load_transactions(files: list[IO], file_types: list[str]) -> pd.DataFrame:

    transactions = map(lambda x: parse_transaction(x[0], x[1]), zip(files, file_types))
    return pd.DataFrame(pd.concat(transactions, axis=0)).sort_index()

def is_pay(x):
    return any([i in  x.lower() for i in ['gusto', 'stripe']])
    income = gains[gains.Name.map(is_pay)]

def is_cc_payment(x):
    banks = ['bill payment bank of america', 'direct debit cardmember']
    return not any([i in x.lower() for i in banks])
    debits = outgoing_ba[outgoing_ba.Name.map(is_cc_payment)]
    debits.loc[:,'Amount'] *= -1

@app.post("/start_config")
def configure():
    history_found = True
    file_ids = [int(x[5:]) for x in request.files.keys()]
    def get_file_type(f: int) -> str:
        t = request.form.get(f'select-{f}')
        if not t:
            raise ValueError(f'Could not load type {f}')
        else:
            return t
    file_types = [get_file_type(x) for x in file_ids]

    def get_file_stream(f: int) -> IO:
        file = request.files.get(f'file-{f}')
        if not file:
            raise ValueError(f'Could not load file {f}')
        else:
            return file.stream

    files = [get_file_stream(f) for f in file_ids]

    current_transactions = load_transactions(files, file_types)

    if request.form.get('reuse_history') == 'on':
        h = load_history()
        if not h:
            history_found = False
        else:
            current_transactions = current_transactions.loc[set(x.id for x in h) - current_transactions.index]
            # if there is no difference between the history and the parsed, go directly to the assessment
            if len(current_transactions) == 0:
                return redirect("assessment")
            # otherwise, go directly to the category selection

    # remove duplicate keys in transactions by summing
    current_transactions = current_transactions.groupby(['date', 'description', 'type']).sum().reset_index()
    current_transactions['date'] = current_transactions['date'].map(lambda x: x.value)
    current_transactions = current_transactions.set_index(['date', 'description', 'type'])

    with init_db() as db:
        # get transactions, diff with those currently stored in database and reindex
        stored_transactions = pd.read_sql('SELECT * FROM transactions', db, index_col=['date', 'description', 'type'], dtype={'amount': float, 'income': bool, 'exclude': bool, 'session_index': int, 'expense_category': str})
        new_indices = [i not in stored_transactions.index for i in current_transactions.index]
        new_transactions = current_transactions[new_indices].reset_index()
        new_transactions['income'] = False
        new_transactions['exclude'] = False
        new_transactions['session_index'] = -1
        new_transactions['expense_category'] = 'none yet'

        all_transactions = pd.concat([new_transactions, stored_transactions.reset_index()], axis=0).set_index(['date', 'description', 'type']).sort_index()
        all_transactions['session_index'] = pd.Series(data=range(len(all_transactions)), index=all_transactions.index)
        for index, amount, income, exclude, session_index, expense_category in all_transactions.itertuples():
            if expense_category == 'none yet':
                db.execute("INSERT INTO transactions(date, description, type, amount, session_index) VALUES(?, ?, ?, ?, ?)", [*index, amount, session_index])
            else:
                db.execute("UPDATE transactions SET session_index = ? WHERE date = ? AND description = ? AND type = ?", [session_index, *index])

        all_transactions = all_transactions.reset_index()
        all_transactions['date'] = all_transactions['date'].map(lambda x: pd.Timestamp(x).strftime("%Y-%m-%d"))
        all_transactions = all_transactions.set_index(['date', 'description', 'type']).sort_index()
        return render_template("category_selection.html", transactions=zip(range(len(all_transactions)), all_transactions.itertuples(index=True)))

@app.post("/category_selection")
def post_category_selection():
    categories = request.form.get("categories")
    return render_template("category_selection.html")

def monthly_charts(transactions: pd.DataFrame) -> dict:
    months = {1: 'jan', 2: 'feb', 3: 'mar', 4: 'apr', 5: 'may', 6: 'jun', 7: 'jul', 8: 'aug', 9: 'sep', 10: 'oct', 11: 'nov', 12: 'dec'}
    expenses = transactions[transactions['income'] == False]
    income = transactions[transactions['income'] == True]
    expense_by_month = -pd.DataFrame(expenses.groupby([expenses['expense_category'], expenses.index.get_level_values(0).month]).sum()[['amount']])
    income_by_month = pd.DataFrame(income.groupby([income['expense_category'], income.index.get_level_values(0).month]).sum()[['amount']])

    month_ids = sorted(list(set(expense_by_month.index.get_level_values(1))))
    n_months = len(month_ids)
    months_axis = [months[m] for m in month_ids]


    income_by_month_no_cats = pd.DataFrame(income.groupby(income.index.get_level_values(0).month).sum()['amount'])
    present_months = set(income_by_month_no_cats.index.get_level_values(0))

    cats_by_total = list(pd.DataFrame(expense_by_month.groupby('expense_category').sum()).sort_values('amount').index)
    cats = list(reversed(cats_by_total.copy()))

    def sort_func(x):
        return [cats_by_total.index(i) for i in x.values]


    # Income and expenses
    expense_by_month_overall = expense_by_month.groupby(level=1).sum()
    expense_by_month_overall_list = [round(expense_by_month_overall.loc[i]['amount'], 3) if i in expense_by_month_overall.index else 0 for i in month_ids]
    income_by_month_overall_list = [round(income_by_month_no_cats.loc[i]['amount'], 3) if i in income_by_month_no_cats.index else 0 for i in month_ids]
    income_and_expenses = [
        {'x': months_axis,
            'y': expense_by_month_overall_list,
            'type': 'bar',
            'text': expense_by_month_overall_list,
            'textposition': 'auto',
            'name': 'expenses'},
        {'x': months_axis,
            'y': income_by_month_overall_list,
            'type': 'bar',
            'text': income_by_month_overall_list,
            'textposition': 'auto',
            'name': 'income'
        }]

    # savings
    s = (income_by_month_no_cats - expense_by_month_overall).fillna(0)['amount'].tolist()
    s = [round(f, 3) for f in s]
    savings = [{'x': months_axis, 'y': s, 'text': s, 'textposition': 'auto', 'type': 'bar', 'name': 'savings'}]

    # cumulative savings
    s = np.cumsum(s).tolist()
    savings_cum = [{'x': months_axis, 'y': s, 'text': s, 'textposition': 'auto', 'type': 'line', 'name': 'savings'}]

    # Expense breakdown
    expense_breakdown = []
    for category in cats_by_total:
        category_expenses = expense_by_month.loc[category]
        expense_breakdown.append(
            {
                'x': months_axis,
                'y': [category_expenses.loc[i]['amount'] if i in category_expenses.index else 0 for i in month_ids],
                'type': 'bar',
                'name': category
            }
        )

    # Income breakdown
    income_breakdown = []
    cats_by_total_income_filtered = [c for c in cats_by_total if c in income_by_month.index.get_level_values(0)]
    print(cats_by_total_income_filtered)
    for category in cats_by_total_income_filtered:
        category_income = income_by_month.loc[category]
        income_breakdown.append(
            {
                'x': months_axis,
                'y': [category_income.loc[i]['amount'] if i in category_income.index else 0 for i in month_ids],
                'type': 'bar',
                'name': category
            }
        )

    return {'income_and_expenses': income_and_expenses,
        'savings': savings,
        'savings_cum': savings_cum,
        'income_breakdown': income_breakdown,
        'expense_breakdown': expense_breakdown}



@app.get("/assessment")
def assessment():
    with db_connect() as db:
        transactions = pd.read_sql("SELECT * FROM transactions WHERE exclude = 0", db)
        transactions['date'] = transactions['date'].map(lambda x: pd.Timestamp(x))
        transactions = transactions.set_index(['date', 'description'])
        mb = monthly_charts(transactions)

        return render_template("assessment.html", **mb)

@app.post("/assessment")
def assessment_post():
    items = [int(x[9:]) for x in request.form.keys() if x[:8] == 'category']
    categories = [request.form.get(f'category-{x}') for x in items]
    excludes = [True if request.form.get(f'exclude-{x}') == 'on' else False for x in items]
    income = [True if request.form.get(f'income-{x}') == 'on' else False for x in items]
    assert(len(categories) == len(excludes))
    assert(len(income) == len(categories))

    with db_connect() as db:
        session_index  = pd.read_sql('SELECT session_index, date, description, type FROM transactions', db, index_col='session_index', dtype={'date': int, 'description': str, 'session_index': int})
        for x in range(len(categories)):
            date = int(session_index.loc[x]['date'])
            description = session_index.loc[x]['description']
            c = categories[x]
            i = income[x]
            e = excludes[x]

            db.execute("UPDATE transactions SET expense_category = ?, income = ?, exclude = ? WHERE date = ? AND description = ?", [c, i, e, date, description])
    return redirect("/assessment")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--cc_path')
    parser.add_argument('-b', '--ba_path')

    return parser.parse_args()
