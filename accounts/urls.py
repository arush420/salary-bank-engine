from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/",                        views.profile_view,    name="profile"),
    path("settings/",                       views.settings_view,   name="settings"),
    path("settings/invite/",               views.invite_user,     name="invite_user"),
    path("settings/role/<int:member_id>/",  views.change_role,     name="change_role"),
    path("settings/deactivate/<int:member_id>/", views.deactivate_user, name="deactivate_user"),
    path("settings/cancel-invite/<int:invite_id>/", views.cancel_invite, name="cancel_invite"),
    path("settings/preferences/",          views.save_preferences, name="save_preferences"),
    path("accept-invite/<uuid:token>/",     views.accept_invite,   name="accept_invite"),
]