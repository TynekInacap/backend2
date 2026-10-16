from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand


DEMO_USERS = (
    ('admin', 'admin123', 'administrador'),
    ('tecnico', 'tecnico123', 'tecnico'),
    ('usuario', 'usuario123', 'usuario'),
)


class Command(BaseCommand):
    help = 'Crea las cuentas de demostración y sus roles si todavía no existen.'

    def handle(self, *args, **options):
        for username, password, role_name in DEMO_USERS:
            role, _ = Group.objects.get_or_create(name=role_name)
            user = User.objects.filter(username=username).first()

            if user is None:
                user = User.objects.create_user(username=username, password=password)
                self.stdout.write(f'Cuenta creada: {username}')
            else:
                self.stdout.write(f'Cuenta existente, contraseña conservada: {username}')

            user.groups.add(role)

        self.stdout.write(self.style.SUCCESS('Cuentas de demostración preparadas.'))
