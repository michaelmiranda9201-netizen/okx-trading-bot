def ensemble_signal(ml, lstm, rules):
    score = (ml * 0.3) + (lstm * 0.5) + (rules * 0.2)

    if score > 0.3:
        return "buy"
    elif score < -0.3:
        return "sell"
    return None