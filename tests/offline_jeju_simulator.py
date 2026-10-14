"""Pure offline inventory simulator. No API, Telegram, or production imports."""
TARGET = '8800286275732'


def transition(previous, observation, barcode=TARGET):
    if barcode != TARGET:
        raise ValueError('wrong product')
    if observation is None:
        return previous, None
    if type(observation) is not int or observation < 0:
        raise ValueError('invalid inventory')
    if previous is not None and (type(previous) is not int or previous < 0):
        raise ValueError('invalid previous inventory')
    if previous is None:
        event = 'FIRST_POSITIVE' if observation > 0 else None
    elif observation > previous:
        event = 'INCREASE'
    elif observation < previous:
        event = 'SOLD_OUT' if observation == 0 else 'DECREASE'
    else:
        event = None
    return observation, event


def apply(state, store_code, observation, barcode=TARGET, delivered=True):
    """Mock alert delivery; failed delivery preserves previous state for retry."""
    previous = state.get(store_code)
    updated, event = transition(previous, observation, barcode)
    if event and not delivered:
        return dict(state), 'ALERT_PENDING'
    result = dict(state)
    if observation is not None:
        result[store_code] = updated
    return result, event
