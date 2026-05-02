from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import os

app = Flask(__name__)
app.secret_key = "secret"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)

# -----------------------
# MODEL
# -----------------------
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float)
    risk = db.Column(db.Integer)
    decision = db.Column(db.String(10))
    reason = db.Column(db.String(100))


class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    high_amount = db.Column(db.Float, default=10000)
    rapid_tx = db.Column(db.Integer, default=5)

# -----------------------
# ROUTES
# -----------------------

@app.route("/")
def home():
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["user"] = request.form["username"]
        return redirect("/dashboard")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    transactions = Transaction.query.order_by(Transaction.id.desc()).all()

    total = len(transactions)
    blocked = len([t for t in transactions if t.decision == "Block"])
    flagged = len([t for t in transactions if t.decision == "Flag"])

    return render_template(
        "dashboard.html",
        transactions=transactions,
        total=total,
        blocked=blocked,
        flagged=flagged
    )


# ✅ CONFIG PAGE
@app.route("/config", methods=["GET", "POST"])
def config():
    cfg = Config.query.first()

    if not cfg:
        cfg = Config()
        db.session.add(cfg)
        db.session.commit()

    if request.method == "POST":
        cfg.high_amount = float(request.form["high_amount"])
        cfg.rapid_tx = int(request.form["rapid_tx"])
        db.session.commit()

        return redirect("/dashboard")

    return render_template("config.html", cfg=cfg)


@app.route("/ping")
def ping():
    return "ok"

# ✅ FIXED ADD TX (ONLY ONE ROUTE — NO DUPLICATES)
@app.route("/add_tx", methods=["POST"])
def add_tx():
    amount = float(request.form["amount"])

    # basic logic (you can improve later)
    cfg = Config.query.first()

    if amount > cfg.high_amount:
        decision = "Block"
        risk = 90
        reason = "High amount"
    elif amount > (cfg.high_amount / 2):
        decision = "Flag"
        risk = 30
        reason = "Medium risk"
    else:
        decision = "Allow"
        risk = 0
        reason = "Normal"

    new_tx = Transaction(
        amount=amount,
        risk=risk,
        decision=decision,
        reason=reason
    )

    db.session.add(new_tx)
    db.session.commit()

    # real-time push
    socketio.emit("new_tx", {
        "id": new_tx.id,
        "amount": new_tx.amount,
        "risk": new_tx.risk,
        "decision": new_tx.decision,
        "reason": new_tx.reason
    })

    return redirect("/dashboard")


# -----------------------
# RUN
# -----------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
