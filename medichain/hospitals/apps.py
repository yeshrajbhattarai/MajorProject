from django.apps import AppConfig
import sys


class HospitalsConfig(AppConfig):
    name = 'hospitals'

    def ready(self):
        if len(sys.argv) > 1 and sys.argv[1] in {
            'makemigrations',
            'migrate',
            'check',
            'collectstatic',
            'shell',
            'test',
        }:
            return

        from django.db.utils import OperationalError, ProgrammingError

        try:
            from .hospital_db import register_db
            from .models import Hospital

            for hospital in Hospital.objects.only('id'):
                register_db(str(hospital.id))
        except (OperationalError, ProgrammingError):
            # App startup can run before migrations in fresh environments.
            return
