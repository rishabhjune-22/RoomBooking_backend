from contextvars import ContextVar


request_id_var = ContextVar("request_id", default="-")


def get_request_id():
    return request_id_var.get()


def set_request_id(request_id):
    return request_id_var.set(request_id)


def reset_request_id(token):
    request_id_var.reset(token)
