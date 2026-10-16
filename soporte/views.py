from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status

from .models import Ticket, TicketCategory, TicketComment, TicketStatusHistory
from .serializer import (
    TicketCategorySerializer,
    TicketCommentSerializer,
    TicketSerializer,
    TicketStatusHistorySerializer,
)


ROLE_LABELS = {
    'administrador': 'Administrador',
    'tecnico': 'Técnico',
    'usuario': 'Usuario',
}


def ensure_default_roles():
    from django.contrib.auth.models import Group

    for name in ROLE_LABELS:
        Group.objects.get_or_create(name=name)


def get_user_role(user):
    if not user.is_authenticated:
        return 'usuario'
    if user.is_superuser:
        return 'administrador'
    groups = user.groups.values_list('name', flat=True)
    for role in ROLE_LABELS:
        if role in groups:
            return role
    return 'usuario'


def can_view_ticket(user, ticket):
    role = get_user_role(user)
    if role == 'administrador':
        return True
    if role == 'tecnico':
        return True
    return ticket.created_by == user.username


def get_role_tickets(user):
    role = get_user_role(user)
    if role == 'administrador':
        return Ticket.objects.all().order_by('-created_at')
    if role == 'tecnico':
        return Ticket.objects.all().order_by('-created_at')
    return Ticket.objects.filter(created_by=user.username).order_by('-created_at')


def can_claim_ticket(ticket, user):
    return (
        get_user_role(user) == 'tecnico'
        and ticket.assigned_to_id is None
        and ticket.status in ['abierto', 'pendiente']
    )


def assign_ticket_to_technician(ticket, technician):
    previous_status = ticket.status
    ticket.assigned_to = technician
    ticket.status = 'en_proceso'
    ticket.save()
    TicketStatusHistory.objects.create(
        ticket=ticket,
        previous_status=previous_status,
        new_status=ticket.status,
        changed_by=technician.username,
    )


def bienvenida(request):
    ensure_default_roles()
    return redirect('login')


def not_found(request, unmatched_path=''):
    return render(request, '404.html', status=404)


def login_view(request):
    ensure_default_roles()

    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Bienvenido, {user.username}.')
            return redirect('dashboard')
        messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'login.html')


def register_view(request):
    ensure_default_roles()

    if request.user.is_authenticated:
        return redirect('dashboard')

    form = UserCreationForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.save()
        from django.contrib.auth.models import Group

        default_group, _ = Group.objects.get_or_create(name='usuario')
        user.groups.add(default_group)
        login(request, user)
        messages.success(request, 'Cuenta creada correctamente. Bienvenido a TicketFlow.')
        return redirect('dashboard')

    if request.method == 'POST':
        messages.error(request, 'No se pudo crear la cuenta. Corrige los datos e inténtalo de nuevo.')

    return render(request, 'register.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required(login_url='login')
def dashboard(request):
    ensure_default_roles()
    tickets = get_role_tickets(request.user)
    role = get_user_role(request.user)

    stats = {
        'total': tickets.count(),
        'abiertos': tickets.filter(status='abierto').count(),
        'en_proceso': tickets.filter(status='en_proceso').count(),
        'resueltos': tickets.filter(status='resuelto').count(),
    }

    return render(
        request,
        'dashboard.html',
        {
            'role': role,
            'role_label': ROLE_LABELS.get(role, 'Usuario'),
            'tickets': tickets[:5],
            'stats': stats,
        },
    )


@login_required(login_url='login')
def tickets_view(request):
    tickets = get_role_tickets(request.user)
    return render(
        request,
        'tickets.html',
        {
            'role': get_user_role(request.user),
            'role_label': ROLE_LABELS.get(get_user_role(request.user), 'Usuario'),
            'tickets': tickets,
        },
    )


@login_required(login_url='login')
def ticket_create(request):
    role = get_user_role(request.user)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        priority = request.POST.get('priority', 'media')
        category_id = request.POST.get('category', '').strip()

        if title and description:
            category = None
            if category_id:
                category = get_object_or_404(TicketCategory, pk=category_id, is_active=True)
            ticket = Ticket.objects.create(
                title=title,
                description=description,
                category=category,
                priority=priority,
                status='abierto',
                created_by=request.user.username,
            )
            TicketStatusHistory.objects.create(
                ticket=ticket,
                previous_status='',
                new_status=ticket.status,
                changed_by=request.user.username,
            )
            messages.success(request, 'Ticket creado correctamente.')
            return redirect('ticket_detail', ticket_id=ticket.pk)

        messages.error(request, 'Debes completar título y descripción.')

    return render(
        request,
        'ticket_form.html',
        {
            'role': role,
            'role_label': ROLE_LABELS.get(role, 'Usuario'),
            'editing': False,
            'categories': TicketCategory.objects.filter(is_active=True).order_by('name'),
        },
    )


@login_required(login_url='login')
def ticket_claim(request, ticket_id):
    if request.method != 'POST' or get_user_role(request.user) != 'tecnico':
        return HttpResponseForbidden()

    ticket = get_object_or_404(Ticket, pk=ticket_id)
    if not can_claim_ticket(ticket, request.user):
        messages.error(request, 'Este ticket ya fue reclamado o no está disponible.')
        return redirect('ticket_detail', ticket_id=ticket.pk)

    assign_ticket_to_technician(ticket, request.user)
    messages.success(request, 'Ticket reclamado y asignado a tu nombre.')
    return redirect('ticket_detail', ticket_id=ticket.pk)


@login_required(login_url='login')
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    if not can_view_ticket(request.user, ticket):
        messages.error(request, 'No tienes permisos para ver este ticket.')
        return redirect('tickets')

    role = get_user_role(request.user)
    can_manage_ticket = role == 'administrador' or (
        role == 'tecnico' and ticket.assigned_to_id == request.user.pk
    )
    can_claim = can_claim_ticket(ticket, request.user)

    if request.method == 'POST':
        if not can_manage_ticket:
            return HttpResponseForbidden()
        if 'message' in request.POST and request.POST.get('message', '').strip():
            TicketComment.objects.create(
                ticket=ticket,
                author=request.user.username,
                message=request.POST.get('message', '').strip(),
            )
            messages.success(request, 'Comentario agregado.')
        elif role in ['administrador', 'tecnico']:
            previous_status = ticket.status
            ticket.status = request.POST.get('status', ticket.status)
            ticket.priority = request.POST.get('priority', ticket.priority)
            ticket.save()
            if ticket.status != previous_status:
                TicketStatusHistory.objects.create(
                    ticket=ticket,
                    previous_status=previous_status,
                    new_status=ticket.status,
                    changed_by=request.user.username,
                )
            messages.success(request, 'Estado del ticket actualizado.')

    comments = ticket.comments.all().order_by('-created_at')
    return render(
        request,
        'ticket_detail.html',
        {
            'ticket': ticket,
            'comments': comments,
            'role': role,
            'role_label': ROLE_LABELS.get(role, 'Usuario'),
            'can_manage_ticket': can_manage_ticket,
            'can_claim': can_claim,
        },
    )


class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all().order_by('-created_at')
    serializer_class = TicketSerializer
    permission_classes = [BasePermission]

    def get_permissions(self):
        return [TicketApiPermission()]

    @action(detail=True, methods=['post'])
    def claim(self, request, pk=None):
        ticket = self.get_object()
        if not can_claim_ticket(ticket, request.user):
            return Response(
                {'detail': 'Este ticket ya fue reclamado o no está disponible.'},
                status=status.HTTP_409_CONFLICT,
            )
        assign_ticket_to_technician(ticket, request.user)
        return Response(self.get_serializer(ticket).data)

    def get_queryset(self):
        return get_role_tickets(self.request.user)

    def perform_create(self, serializer):
        ticket = serializer.save(created_by=self.request.user.username)
        TicketStatusHistory.objects.create(
            ticket=ticket,
            previous_status='',
            new_status=ticket.status,
            changed_by=self.request.user.username,
        )

    def perform_update(self, serializer):
        previous_status = serializer.instance.status
        ticket = serializer.save()
        if ticket.status != previous_status:
            TicketStatusHistory.objects.create(
                ticket=ticket,
                previous_status=previous_status,
                new_status=ticket.status,
                changed_by=self.request.user.username,
            )


class TicketCommentViewSet(viewsets.ModelViewSet):
    queryset = TicketComment.objects.all().order_by('-created_at')
    serializer_class = TicketCommentSerializer

    def get_permissions(self):
        return [CommentApiPermission()]

    def get_queryset(self):
        tickets = get_role_tickets(self.request.user)
        return TicketComment.objects.filter(ticket__in=tickets).order_by('-created_at')

    def perform_create(self, serializer):
        ticket = serializer.validated_data['ticket']
        if not get_role_tickets(self.request.user).filter(pk=ticket.pk).exists():
            raise PermissionDenied('No tienes permisos para comentar este ticket.')
        if (
            get_user_role(self.request.user) == 'tecnico'
            and ticket.assigned_to_id != self.request.user.pk
        ):
            raise PermissionDenied('Debes reclamar el ticket antes de comentar.')
        serializer.save(author=self.request.user.username)


class TicketApiPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        role = get_user_role(request.user)
        if getattr(view, 'action', None) == 'claim':
            return role == 'tecnico'
        if request.method in SAFE_METHODS:
            return True
        if request.method == 'POST':
            return role in ['administrador', 'usuario']
        return role in ['administrador', 'tecnico']

    def has_object_permission(self, request, view, ticket):
        role = get_user_role(request.user)
        if role == 'administrador':
            return True
        if role == 'tecnico':
            if getattr(view, 'action', None) == 'claim':
                return can_claim_ticket(ticket, request.user)
            return request.method in SAFE_METHODS or ticket.assigned_to_id == request.user.pk
        return request.method in SAFE_METHODS and ticket.created_by == request.user.username


class CommentApiPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return get_user_role(request.user) in ['administrador', 'tecnico']

    def has_object_permission(self, request, view, comment):
        role = get_user_role(request.user)
        if role == 'administrador':
            return True
        if role == 'tecnico':
            return request.method in SAFE_METHODS or comment.ticket.assigned_to_id == request.user.pk
        return request.method in SAFE_METHODS and comment.ticket.created_by == request.user.username


class TicketCategoryPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.method in SAFE_METHODS or get_user_role(request.user) == 'administrador'


class TicketCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = TicketCategorySerializer

    def get_permissions(self):
        return [TicketCategoryPermission()]

    def get_queryset(self):
        categories = TicketCategory.objects.all().order_by('name')
        if get_user_role(self.request.user) != 'administrador':
            categories = categories.filter(is_active=True)
        return categories


class TicketStatusHistoryPermission(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated


class TicketStatusHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TicketStatusHistorySerializer
    permission_classes = [TicketStatusHistoryPermission]

    def get_queryset(self):
        tickets = get_role_tickets(self.request.user)
        return TicketStatusHistory.objects.filter(ticket__in=tickets).order_by('-changed_at')
