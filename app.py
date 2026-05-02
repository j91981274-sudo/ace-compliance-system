kfrom flask import Flask, render_template, request, redirect, session, Response
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
# MODELS
# -----------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))
    is_premium = db.Column(db.Boolean, default=False)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float)
    risk = db.Column(db.Integer)
    decision = db.Column(db.String(10))
    reason = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))


class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    high_amount = db.Column(db.Float, default=10000)


# -----------------------
# ROUTES
# -----------------------

@app.route("/")
def home():
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if not user:
            user = User(username=username, password=password)
            db.session.add(user)
            db.session.commit()

        session["user_id"] = user.id
        return redirect("/dashboard")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    transactions = Transaction.query.filter_by(
        user_id=session["user_id"]
    ).all()

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


@app.route("/config", methods=["GET", "POST"])
def config():
    cfg = Config.query.first()

    if not cfg:
        cfg = Config()
        db.session.add(cfg)
        db.session.commit()

    if request.method == "POST":
        cfg.high_amount = float(request.form["high_amount"])
        db.session.commit()
        return redirect("/dashboard")

    return render_template("config.html", cfg=cfg)


@app.route("/add_tx", methods=["POST"])
def add_tx():
    if "user_id" not in session:
        return redirect("/login")

    try:
        amount = float(request.form["amount"])
    except:
        return redirect("/dashboard")

    cfg = Config.query.first()

    # auto-create config if missing
    if not cfg:
        cfg = Config(high_amount=10000)
        db.session.add(cfg)
        db.session.commit()

    # 🔥 smarter fraud logic
    recent = Transaction.query.filter_by(
        user_id=session["user_id"]
    ).order_by(Transaction.id.desc()).limit(3).all()

    rapid = len(recent) >= 3 and all(t.amount < 500 for t in recent)

    if amount > cfg.high_amount:
        decision = "Block"
        risk = 90
        reason = "High amount"

    elif rapid:
        decision = "Flag"
        risk = 50
        reason = "Rapid transactions"

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
        reason=reason,
        user_id=session["user_id"]
    )

    db.session.add(new_tx)
    db.session.commit()

    return redirect("/dashboard")


@app.route("/export")
def export():
    if "user_id" not in session:
        return redirect("/login")

    user = User.query.get(session["user_id"])

    if not user.is_premium:
        return "Upgrade to premium to export data"

    transactions = Transaction.query.filter_by(
        user_id=session["user_id"]
    ).all()

    def generate():
        yield "ID,Amount,Risk,Decision,Reason\n"
        for t in transactions:
            yield f"{t.id},{t.amount},{t.risk},{t.decision},{t.reason}\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=data.csv"}
    )


@app.route("/upgrade")
def upgrade():
    if "user_id" not in session:
        return redirect("/login")

    user = User.query.get(session["user_id"])
    user.is_premium = True
    db.session.commit()

    return redirect("/dashboard")


# TEMP FIX ROUTE (use once, then remove)
@app.route("/reset")
def reset():
    db.drop_all()
    db.create_all()
    return "DB Reset Done"


# -----------------------
# RUN
# -----------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
