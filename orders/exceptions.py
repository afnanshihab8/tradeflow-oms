class OrderServiceError(Exception):
    status_code = 400

    def __init__(self, code, detail, *, errors=None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.errors = errors

    def as_response_data(self):
        return {"code": self.code, "detail": self.detail, "errors": self.errors}


class OrderConflictError(OrderServiceError):
    status_code = 409
