from django.urls import path
from . import views

urlpatterns = [
    path("approvals/", views.approval_queue, name="approval_queue"),
    path("approve/<int:id>/", views.approve_request, name="approve_request"),
]
