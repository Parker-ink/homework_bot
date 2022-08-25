class ResponseNotOK(Exception):
    pass


def response_not_ok(value):
    if value != 200:
        raise ResponseNotOK('Ошибка соединения')
