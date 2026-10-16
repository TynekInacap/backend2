from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Ticket, TicketCategory, TicketStatusHistory


class SupportTicketAppTests(TestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='administrador')
        self.tecnico_group, _ = Group.objects.get_or_create(name='tecnico')
        self.usuario_group, _ = Group.objects.get_or_create(name='usuario')

        self.admin = User.objects.create_user(username='admin', password='admin123')
        self.admin.groups.add(self.admin_group)

        self.tecnico = User.objects.create_user(username='tecnico', password='tecnico123')
        self.tecnico.groups.add(self.tecnico_group)

        self.usuario = User.objects.create_user(username='usuario', password='usuario123')
        self.usuario.groups.add(self.usuario_group)

    def test_home_page_loads(self):
        response = self.client.get(reverse("bienvenida"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/login/")

    def test_login_page_loads(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_unknown_url_shows_generic_not_found_page(self):
        response = self.client.get('/login/4343')

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, '404 - Página no encontrada', status_code=404)
        self.assertNotContains(response, 'Request URL', status_code=404)

    def test_missing_ticket_shows_generic_not_found_page(self):
        self.client.force_login(self.usuario)

        response = self.client.get('/tickets/999999/')

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, '404 - Página no encontrada', status_code=404)
        self.assertNotContains(response, 'Request URL', status_code=404)

    def test_admin_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_ticket_api_list_endpoint_is_available(self):
        self.client.force_login(self.usuario)
        response = self.client.get("/api/tickets/")
        self.assertEqual(response.status_code, 200)

    def test_ticket_api_requires_authentication(self):
        response = self.client.get('/api/tickets/')
        self.assertIn(response.status_code, [401, 403])

    def test_user_cannot_read_another_users_ticket_through_api(self):
        ticket = Ticket.objects.create(
            title='Ticket privado',
            description='Solicitud de administrador',
            created_by=self.admin.username,
        )
        self.client.force_login(self.usuario)

        response = self.client.get(f'/api/tickets/{ticket.pk}/')

        self.assertEqual(response.status_code, 404)

    def test_ticket_api_sets_owner_from_authenticated_user(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            '/api/tickets/',
            {
                'title': 'Ticket propio',
                'description': 'Creado desde la API',
                'created_by': self.admin.username,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Ticket.objects.get(pk=response.json()['id']).created_by, self.usuario.username)

    def test_admin_can_manage_categories_but_regular_user_cannot(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            '/api/categories/',
            {'name': 'Redes', 'description': 'Conectividad', 'is_active': True},
        )
        self.assertEqual(response.status_code, 201)

        self.client.force_login(self.usuario)
        response = self.client.post(
            '/api/categories/',
            {'name': 'No autorizada', 'description': '', 'is_active': True},
        )
        self.assertEqual(response.status_code, 403)

    def test_status_history_api_is_read_only_and_scoped(self):
        ticket = Ticket.objects.create(
            title='Ticket con historial',
            description='Historial visible al propietario.',
            created_by=self.usuario.username,
        )
        TicketStatusHistory.objects.create(
            ticket=ticket,
            new_status='abierto',
            changed_by=self.usuario.username,
        )
        self.client.force_login(self.usuario)

        response = self.client.get('/api/status-history/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(self.client.post('/api/status-history/', {}).status_code, 405)

    def test_initial_categories_fixture_loads(self):
        call_command('loaddata', 'initial_categories', verbosity=0)
        self.assertEqual(TicketCategory.objects.count(), 4)

    def test_ticket_category_can_be_assigned_on_creation(self):
        category = TicketCategory.objects.create(name='Hardware')
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('ticket_create'),
            {
                'title': 'Equipo no enciende',
                'description': 'El equipo no inicia.',
                'priority': 'alta',
                'category': category.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        ticket = Ticket.objects.get(title='Equipo no enciende')
        self.assertEqual(ticket.category, category)
        self.assertTrue(ticket.status_history.filter(new_status='abierto').exists())

    def test_status_change_creates_history_entry(self):
        ticket = Ticket.objects.create(
            title='Ticket para seguimiento',
            description='Cambio de estado de prueba.',
            created_by=self.admin.username,
            assigned_to=self.tecnico,
            status='en_proceso',
        )
        self.client.force_login(self.tecnico)

        response = self.client.post(
            reverse('ticket_detail', args=[ticket.pk]),
            {'status': 'resuelto', 'priority': 'media'},
        )

        self.assertEqual(response.status_code, 200)
        history = TicketStatusHistory.objects.get(ticket=ticket, new_status='resuelto')
        self.assertEqual(history.previous_status, 'en_proceso')
        self.assertEqual(history.changed_by, self.tecnico.username)

    def test_technician_can_see_tickets_from_all_users(self):
        own_ticket = Ticket.objects.create(
            title='Ticket propio',
            description='Creado por técnico',
            created_by=self.tecnico.username,
            status='cerrado',
        )
        user_ticket = Ticket.objects.create(
            title='Ticket de usuario',
            description='Creado por usuario',
            created_by=self.usuario.username,
            status='abierto',
        )
        self.client.force_login(self.tecnico)

        response = self.client.get(reverse('tickets'))

        self.assertContains(response, own_ticket.title)
        self.assertContains(response, user_ticket.title)

    def test_user_sees_only_their_own_open_and_closed_tickets(self):
        own_open_ticket = Ticket.objects.create(
            title='Ticket propio abierto',
            description='Abierto',
            created_by=self.usuario.username,
            status='abierto',
        )
        own_closed_ticket = Ticket.objects.create(
            title='Ticket propio cerrado',
            description='Cerrado',
            created_by=self.usuario.username,
            status='cerrado',
        )
        other_ticket = Ticket.objects.create(
            title='Ticket ajeno',
            description='Pertenece a otra cuenta',
            created_by=self.admin.username,
            status='abierto',
        )
        self.client.force_login(self.usuario)

        response = self.client.get(reverse('tickets'))

        self.assertContains(response, own_open_ticket.title)
        self.assertContains(response, own_closed_ticket.title)
        self.assertNotContains(response, other_ticket.title)

    def test_technician_can_claim_ticket(self):
        ticket = Ticket.objects.create(
            title='Ticket sin asignar',
            description='Debe ser reclamable.',
            created_by=self.usuario.username,
        )
        self.client.force_login(self.tecnico)

        response = self.client.post(reverse('ticket_claim', args=[ticket.pk]))

        self.assertRedirects(response, reverse('ticket_detail', args=[ticket.pk]))
        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_to, self.tecnico)
        self.assertEqual(ticket.status, 'en_proceso')
        self.assertTrue(ticket.status_history.filter(new_status='en_proceso').exists())

    def test_technician_can_claim_ticket_through_api(self):
        ticket = Ticket.objects.create(
            title='Ticket reclamado por API',
            description='Debe quedar asignado.',
            created_by=self.usuario.username,
        )
        self.client.force_login(self.tecnico)

        response = self.client.post(f'/api/tickets/{ticket.pk}/claim/')

        self.assertEqual(response.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_to, self.tecnico)
        self.assertEqual(ticket.status, 'en_proceso')

    def test_user_cannot_comment_on_own_ticket(self):
        ticket = Ticket.objects.create(
            title='Ticket del usuario',
            description='El usuario solo debe consultar.',
            created_by=self.usuario.username,
        )
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('ticket_detail', args=[ticket.pk]),
            {'message': 'Comentario que debe rechazarse'},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ticket.comments.exists())

    def test_user_cannot_update_own_ticket_through_api(self):
        ticket = Ticket.objects.create(
            title='Ticket protegido',
            description='Solo lectura para su dueño.',
            created_by=self.usuario.username,
        )
        self.client.force_login(self.usuario)

        response = self.client.patch(
            f'/api/tickets/{ticket.pk}/',
            {'status': 'cerrado'},
            content_type='application/json',
        )

        self.assertIn(response.status_code, [401, 403])
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'abierto')

    def test_user_can_register_and_get_default_role(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "nuevousuario",
                "password1": "Segura2024!",
                "password2": "Segura2024!",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username='nuevousuario').exists())
        user = User.objects.get(username='nuevousuario')
        self.assertTrue(user.groups.filter(name='usuario').exists())

    def test_seed_demo_users_creates_working_role_accounts(self):
        User.objects.filter(username__in=['admin', 'tecnico', 'usuario']).delete()

        call_command('seed_demo_users', verbosity=0)

        for username, password, role in (
            ('admin', 'admin123', 'administrador'),
            ('tecnico', 'tecnico123', 'tecnico'),
            ('usuario', 'usuario123', 'usuario'),
        ):
            with self.subTest(username=username):
                authenticated_user = authenticate(username=username, password=password)
                self.assertIsNotNone(authenticated_user)
                self.assertTrue(authenticated_user.groups.filter(name=role).exists())
