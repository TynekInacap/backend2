from django.conf import settings
from django.db import models
from django.utils import timezone


class TicketCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class Ticket(models.Model):
    PRIORITY_CHOICES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ]

    STATUS_CHOICES = [
        ('abierto', 'Abierto'),
        ('en_proceso', 'En proceso'),
        ('pendiente', 'Pendiente'),
        ('resuelto', 'Resuelto'),
        ('cerrado', 'Cerrado'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(
        TicketCategory,
        related_name='tickets',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='assigned_tickets',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='media')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='abierto')
    created_by = models.CharField(max_length=150, default='usuario')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.title}'


class TicketStatusHistory(models.Model):
    ticket = models.ForeignKey(Ticket, related_name='status_history', on_delete=models.CASCADE)
    previous_status = models.CharField(max_length=20, blank=True, default='')
    new_status = models.CharField(max_length=20, choices=Ticket.STATUS_CHOICES)
    changed_by = models.CharField(max_length=150)
    changed_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.ticket.title}: {self.previous_status or "Nuevo"} -> {self.new_status}'


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, related_name='comments', on_delete=models.CASCADE)
    author = models.CharField(max_length=150)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.author} - {self.ticket.title}'
