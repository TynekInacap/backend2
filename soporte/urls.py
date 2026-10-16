from django.shortcuts import redirect
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    TicketCategoryViewSet,
    TicketCommentViewSet,
    TicketStatusHistoryViewSet,
    TicketViewSet,
    bienvenida,
    dashboard,
    login_view,
    logout_view,
    not_found,
    register_view,
    ticket_claim,
    ticket_create,
    ticket_detail,
    tickets_view,
)

router = DefaultRouter()
router.register(r'categories', TicketCategoryViewSet, basename='ticket-category')
router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'comments', TicketCommentViewSet, basename='ticket-comment')
router.register(r'status-history', TicketStatusHistoryViewSet, basename='ticket-status-history')

urlpatterns = [
    path('', lambda request: redirect('login'), name='bienvenida'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
    path('tickets/', tickets_view, name='tickets'),
    path('tickets/crear/', ticket_create, name='ticket_create'),
    path('tickets/<int:ticket_id>/reclamar/', ticket_claim, name='ticket_claim'),
    path('tickets/<int:ticket_id>/', ticket_detail, name='ticket_detail'),
    path('api/', include(router.urls)),
    path('<path:unmatched_path>', not_found, name='not_found'),
]
