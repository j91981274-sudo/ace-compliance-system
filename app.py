from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ace.db'
db = SQLAlchemy(app)

# ------------------ MODELS ------------------

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer)
    receiver_id = db.Column(db.Integer)
    amount = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    risk_score = db.Column(db.Integer)
    decision = db.Column(db.String(20))


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer)
    action = db.Column(db.String(50))
    reason = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.now)


class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    high_amount = db.Column(db.Integer, default=100000)
    rapid_tx_count = db.Column(db.Integer, default=3)


# ------------------ RISK ENGINE ------------------

def calculate_risk(sender_id, amount):
    config = Config.query.first()
    score = 0

    if amount > config.high_amount:
        score += 70

    one_hour_ago = datetime.now() - timedelta(hours=1)
    recent = Transaction.query.filter(
        Transaction.sender_id == sender_id,
        Transaction.timestamp >= one_hour_ago
    ).count()

    if recent >= config.rapid_tx_count:
        score += 30

    return score


# ------------------ DECISION ENGINE ------------------

def make_decision(score):
    if score >= 70:
        return "Block"
    elif score >= 20:
        return "Flag"
    else:
        return "Allow"


# ------------------ ACTION ------------------

def log_action(tx_id, action, reason):
    log = AuditLog(
        transaction_id=tx_id,
        action=action,
        reason=reason
    )
    db.session.add(log)
    db.session.commit()


# ------------------ ROUTES ------------------

@app.route('/')
def home():
    return {"system": "ACE running"}


@app.route('/transaction', methods=['POST'])
def process_transaction():
    data = request.json

    score = calculate_risk(data['sender_id'], data['amount'])
    decision = make_decision(score)

    tx = Transaction(
        sender_id=data['sender_id'],
        receiver_id=data['receiver_id'],
        amount=data['amount'],
        risk_score=score,
        decision=decision
    )

    db.session.add(tx)
    db.session.commit()

    if decision == "Block":
        log_action(tx.id, "Blocked", "High risk")
    elif decision == "Flag":
        log_action(tx.id, "Flagged", "Suspicious pattern")
    else:
        log_action(tx.id, "Allowed", "Low risk")

    return jsonify({
        "transaction_id": tx.id,
        "risk_score": score,
        "decision": decision
    })


@app.route('/dashboard')
def dashboard():
    transactions = Transaction.query.all()
    logs = AuditLog.query.all()

    return render_template(
        'dashboard.html',
        transactions=transactions,
        logs=logs
    )


@app.route('/config')
def config_page():
    config = Config.query.first()
    return render_template('config.html', config=config)


@app.route('/update_config', methods=['POST'])
def update_config():
    config = Config.query.first()

    config.high_amount = int(request.form['high_amount'])
    config.rapid_tx_count = int(request.form['rapid_tx_count'])

    db.session.commit()

    return render_template(
        'config.html',
        config=config,
        message="✅ Rules updated"
    )


# 🔥 NEW: suspicious only endpoint
@app.route('/suspicious')
def suspicious():
    txs = Transaction.query.filter(Transaction.decision != "Allow").all()

    return jsonify([
        {
            "id": t.id,
            "amount": t.amount,
            "risk": t.risk_score,
            "decision": t.decision
        } for t in txs
    ])


# 🔥 NEW: simulate transactions
@app.route('/simulate')
def simulate():
    for i in range(5):
        tx = Transaction(
            sender_id=99,
            receiver_id=2,
            amount=20000,
            risk_score=30,
            decision="Flag"
        )
        db.session.add(tx)

    db.session.commit()
    return {"message": "Simulation complete"}


# ------------------ INIT ------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        if not Config.query.first():
            db.session.add(Config())
            db.session.commit()

    app.run(debug=True)
