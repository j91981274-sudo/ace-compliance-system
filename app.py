from flask import Flask, request, jsonify, render_template, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from collections import defaultdict
import random

app = Flask(__name__)
app.secret_key = "supersecret"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ace.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =========================
# MODELS
# =========================

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer)
    receiver_id = db.Column(db.Integer)
    amount = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    risk_score = db.Column(db.Integer)
    decision = db.Column(db.String(20))
    reason = db.Column(db.String(100))


class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    high_amount = db.Column(db.Float, default=100000)
    rapid_tx_count = db.Column(db.Integer, default=5)


# =========================
# AUTH
# =========================

USERNAME = "admin"
PASSWORD = "admin123"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == USERNAME and request.form['password'] == PASSWORD:
            session['user'] = USERNAME
            return redirect('/dashboard')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# =========================
# RISK ENGINE
# =========================

def calculate_risk(sender_id, amount):
    config = Config.query.first()

    if not config:
        config = Config()
        db.session.add(config)
        db.session.commit()

    if amount > config.high_amount:
        return 100, "High amount transaction"

    recent = Transaction.query.filter(
        Transaction.sender_id == sender_id,
        Transaction.timestamp >= datetime.utcnow() - timedelta(minutes=1)
    ).count()

    if recent >= config.rapid_tx_count:
        return 70, "Suspicious pattern"

    return 0, "Low risk"


# =========================
# ROUTES
# =========================

@app.route('/')
def home():
    return jsonify({"system": "ACE running"})


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    transactions = Transaction.query.order_by(Transaction.id.desc()).all()

    total = len(transactions)
    blocked = sum(1 for t in transactions if t.decision == "Block")
    flagged = sum(1 for t in transactions if t.decision == "Flag")
    allow = sum(1 for t in transactions if t.decision == "Allow")

    # REAL trend grouping
    buckets = defaultdict(int)
    for t in transactions:
        key = t.timestamp.strftime("%H:%M")
        buckets[key] += 1

    timestamps = list(buckets.keys())
    counts = list(buckets.values())

    return render_template(
        "dashboard.html",
        transactions=transactions,
        total=total,
        blocked=blocked,
        flagged=flagged,
        allow=allow,
        flag=flagged,
        block=blocked,
        timestamps=timestamps,
        counts=counts
    )


@app.route('/transaction', methods=['POST'])
def transaction():
    data = request.json

    risk, reason = calculate_risk(data['sender_id'], data['amount'])

    if risk >= 100:
        decision = "Block"
    elif risk >= 50:
        decision = "Flag"
    else:
        decision = "Allow"

    tx = Transaction(
        sender_id=data['sender_id'],
        receiver_id=data['receiver_id'],
        amount=data['amount'],
        risk_score=risk,
        decision=decision,
        reason=reason
    )

    db.session.add(tx)
    db.session.commit()

    return jsonify({
        "decision": decision,
        "risk_score": risk,
        "transaction_id": tx.id
    })


# =========================
# 🔥 SIMULATION ROUTE
# =========================

@app.route('/simulate')
def simulate():
    for _ in range(5):
        sender = random.randint(1, 5)
        receiver = random.randint(1, 5)
        amount = random.choice([5000, 20000, 60000, 200000])

        risk, reason = calculate_risk(sender, amount)

        if risk >= 100:
            decision = "Block"
        elif risk >= 50:
            decision = "Flag"
        else:
            decision = "Allow"

        tx = Transaction(
            sender_id=sender,
            receiver_id=receiver,
            amount=amount,
            risk_score=risk,
            decision=decision,
            reason=reason
        )

        db.session.add(tx)

    db.session.commit()
    return jsonify({"status": "simulated"})


# =========================
# INIT
# =========================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        if not Config.query.first():
            db.session.add(Config())
            db.session.commit()

        if not Transaction.query.first():
            sample = [
                Transaction(sender_id=1, receiver_id=2, amount=5000, risk_score=0, decision="Allow", reason="Low risk"),
                Transaction(sender_id=2, receiver_id=3, amount=20000, risk_score=0, decision="Allow", reason="Low risk"),
                Transaction(sender_id=3, receiver_id=4, amount=200000, risk_score=100, decision="Block", reason="High amount transaction"),
            ]
            db.session.add_all(sample)
            db.session.commit()

    app.run(host='0.0.0.0', port=5000)
