import argparse, os, sqlite3
from typing import IO, Optional, Set
from matplotlib import pyplot as plt
from flask import Flask, render_template, redirect, request, session
import pandas as pd
from transaction_parsers import parse_transaction
from werkzeug.datastructures import FileStorage

app = Flask(__name__)
app.secret_key = 'db2c0d8a-275c-11ef-b5da-e32f975dcd51'

@app.route("/")
def start_page():
    #TODO: implement startup business logic
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

    # remove duplicate keys in transactions
    current_transactions = current_transactions.groupby(['date', 'description', 'type']).sum()
    with init_db() as db:
        stored_transactions = pd.read_sql('SELECT * FROM transactions', db, index_col=['date', 'description', 'type'], parse_dates=['date'])
        new_indices = [i not in stored_transactions.index for i in current_transactions.index]
        new_transactions = current_transactions[new_indices].reset_index()
        new_transactions['date'] = new_transactions['date'].map(lambda x: x.value)
        new_transactions.to_sql(name='transactions', con=db, if_exists='append', index=False)
        order_to_index = {x: i for x, i in enumerate(current_transactions.index)}
        session['order_to_index'] = order_to_index
        return render_template("category_selection.html", transactions=zip(range(len(current_transactions)), current_transactions.itertuples(index=True)))

@app.post("/category_selection")
def post_category_selection():
    categories = request.form.get("categories")
    return render_template("category_selection.html")

def monthly_breakdown(transactions: pd.DataFrame):
    months = {1: 'jan', 2: 'feb', 3: 'mar', 4: 'apr', 5: 'may', 6: 'jun', 7: 'jul', 8: 'aug', 9: 'sep', 10: 'oct', 11: 'nov', 12: 'dec'}
    expenses = transactions[transactions['expese'] == True]
    income = transactions[transactions['income'] == True]
    #expense_by_month = expenses.groupby([expenses.])

@app.get("/assessment")
def assessment():
    with db_connect() as db:
        transactions = pd.read_sql("SELECT * FROM transactions", db, index_col=['date', 'description'])
        monthly_breakdown = monthly_breakdown(transactions)

        return render_template("assessment.html", expenses=expenses)

@app.post("/assessment")
def assessment_post():
    items = [int(x[9:]) for x in request.form.keys() if x[:8] == 'category']
    categories = [request.form.get(f'category-{x}') for x in items]
    excludes = [True if request.form.get(f'exclude{x}') == 'on' else False for x in items]
    income = [True if request.form.get(f'income-{x}') == 'on' else False for x in items]
    assert(len(categories) == len(excludes))
    assert(len(income) == len(categories))

    order_to_index = session['order_to_index']

    with db_connect() as db:
        for x in range(len(categories)):
            index = order_to_index[str(x)][:2]

            c = categories[x]
            i = income[x]
            e = excludes[x]

            print(index)
            print(db.execute("SELECT * FROM transactions WHERE date = ? AND description = ?", index).fetchall())
            if e:
                # somehow we need to identify the rows in the table with the past request. Maybe a session key?
                db.execute("DELETE FROM transactions WHERE date = ? AND description = ?", index)
            else:
                db.execute("UPDATE transactions SET expense_category = ?, income = ? WHERE date = ? AND description = ?", (c, i, *index))
    return redirect("/assessment")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--cc_path')
    parser.add_argument('-b', '--ba_path')

    return parser.parse_args()
