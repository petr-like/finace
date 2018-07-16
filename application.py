import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Ensure environment variable is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    history = db.execute(
        "SELECT symbol, SUM(amount) AS amount FROM transactions WHERE user_id = :id GROUP BY symbol HAVING sum(amount) > 0", id=session["user_id"])
    all_action_summ = 0
    for h in history:
        res = lookup(h['symbol'])
        h["price"] = res['price']
        h["total"] = h["amount"] * res["price"]
        all_action_summ += h["total"]

    cash = cash[0]["cash"]
    all_action_summ += cash

    return render_template("index.html", history=history, all_action_summ=all_action_summ, cash=cash)

    # return apology("todo")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        amount = request.form.get("shares")

        if not symbol:
            return apology("must provide symbol")
        res = lookup(symbol)
        if not res:
            return apology("must provide correct symbol")
        if not amount:
            return apology("must provide amount shares", 400)
        if not amount.isdigit():
            return apology("Iput a number positive", 400)

        price = res['price']
        summ = price * (float(amount) * 1.00)
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        action = db.execute("SELECT symbol FROM transactions WHERE id = :id", id=session["user_id"])
        if cash[0]['cash'] < summ:
            return apology("Need more money")
        db.execute("""
            INSERT INTO transactions(symbol, price, amount, user_id, total)
            VALUES(:symbol, :price, :amount, :user_id, :summ)
        """, symbol=symbol, price=price, amount=amount, user_id=session["user_id"], summ=summ)
        db.execute("UPDATE users SET cash=cash-:summ WHERE id = :id", summ=summ, id=session["user_id"])
        flash('Bought!')
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    history = db.execute("SELECT * FROM transactions WHERE user_id = :id", id=session["user_id"])
    # for h in history:
    #     res = lookup(h['symbol'])
    #     h['price'] = res['price']

    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("must provide symbol")
        res = lookup(symbol)
        if not res:
            return apology("must provide correct symbol")
        return render_template("quoted.html", **res)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
     # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        password_confirmate = request.form.get("confirmation")
        # ensure username was submitted
        if not username:
            return apology("must provide username")
        # ensure password was submitted
        elif not password:
            return apology("must provide password")
            # ensure password was submitted
        elif password != password_confirmate:
            return apology("must confirm password")
        elif db.execute("SELECT username FROM users WHERE username LIKE :username", username=request.form.get('username')):
            return apology("Username taken")

        # query database for username
        rows = db.execute("""
            INSERT INTO users(username, hash)
            VALUES(:username, :hash)
        """, username=username, hash=generate_password_hash(password))

        # Forget any user_id
        session.clear()

        rows_login = db.execute("SELECT * FROM users WHERE username = :username",
                                username=request.form.get("username"))

        # Remember which user has logged in
        session["user_id"] = rows_login[0]["id"]

        # redirect user to home page
        flash('Registered!')
        return redirect("/")

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        amount = int(request.form.get("shares"))
        user_shares = db.execute(
            "SELECT sum(amount) as amount FROM transactions WHERE user_id = :id and symbol = :symbol GROUP BY symbol", id=session["user_id"], symbol=symbol)
        if not symbol:
            return apology("must provide symbol")
        res = lookup(symbol)
        if not res:
            return apology("must provide correct symnew-password-confirmate")

        if not amount:
            return apology("must provide amount shares")

        if amount > user_shares[0]['amount']:
            return apology("Don't have how much")

        price = res['price']

        summ = price * (float(amount) * 1.00)
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

        db.execute("""
            INSERT INTO transactions(symbol, price, amount, user_id, total)
            VALUES(:symbol, :price, :amount*-1, :user_id, :summ)
        """, symbol=symbol, price=price, amount=amount, user_id=session["user_id"], summ=summ)
        db.execute("UPDATE users SET cash=cash+:summ WHERE id = :id", summ=summ, id=session["user_id"])
        flash('Sold!')
        return redirect("/")
    else:

        user_shares = db.execute("SELECT symbol FROM transactions WHERE user_id = :id  GROUP BY symbol", id=session["user_id"])

        return render_template("sell.html", symbol=user_shares)


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change password."""
    if request.method == "POST":
        old_password = request.form.get("password")
        new_password = request.form.get("new-password")
        new_password_confirmate = request.form.get("confirmation")
        if not old_password:
            return apology("must provide your password")
        # ensure password was submitted
        elif not new_password:
            return apology("must provide new password")
            # ensure password was submitted
        elif new_password != new_password_confirmate:
            return apology("your new password not confirmate")

        rows = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        if not check_password_hash(rows[0]["hash"], old_password):
            return apology("your password wrong")

        db.execute("UPDATE users SET hash = :hash WHERE id = :id", hash=generate_password_hash(new_password), id=session["user_id"])
        return redirect("/")
    else:
        return render_template("change_password.html")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
