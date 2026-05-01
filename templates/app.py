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

    return {"message": "Configuration updated successfully"}
