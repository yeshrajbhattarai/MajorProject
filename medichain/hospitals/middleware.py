from .db_router import clear_hospital_db, set_hospital_db


class HospitalDBContextMiddleware:
    """Attach hospital context for DB routing during each request lifecycle."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        hospital_id = request.session.get('hospital_id')
        if hospital_id:
            set_hospital_db(hospital_id)
        try:
            return self.get_response(request)
        finally:
            clear_hospital_db()
