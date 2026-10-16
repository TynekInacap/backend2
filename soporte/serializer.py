from rest_framework import serializers

from .models import Ticket, TicketCategory, TicketComment, TicketStatusHistory


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = '__all__'
        read_only_fields = ('created_by', 'assigned_to', 'created_at', 'updated_at')


class TicketCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketComment
        fields = '__all__'
        read_only_fields = ('author', 'created_at')


class TicketCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketCategory
        fields = '__all__'


class TicketStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketStatusHistory
        fields = '__all__'
        read_only_fields = ('previous_status', 'new_status', 'changed_by', 'changed_at')