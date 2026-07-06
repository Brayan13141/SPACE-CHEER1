from django.urls import path
from social import views

app_name = "social"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("post/nuevo/", views.post_create, name="post_create"),
    path("post/<int:pk>/", views.post_detail, name="post_detail"),
    path("post/<int:pk>/like/", views.post_like_toggle, name="post_like"),
    path("post/<int:pk>/comentar/", views.comment_create, name="comment_create"),
    path("post/<int:pk>/compartir/", views.repost_create, name="repost_create"),
    path("post/<int:pk>/eliminar/", views.post_delete, name="post_delete"),
    path("comentario/<int:pk>/eliminar/", views.comment_delete, name="comment_delete"),
    path("ranking/", views.team_ranking, name="team_ranking"),
    path("invite/", views.send_invite, name="send_invite"),
    path("perfil/", views.profile_me, name="profile_me"),
    path("perfil/<str:username>/", views.profile_detail, name="profile_detail"),
    path("equipos/", views.team_directory, name="team_directory"),
    path("equipo/<int:pk>/", views.team_page, name="team_page"),
    path("notificaciones/", views.notifications, name="notifications"),
    path("notificaciones/<int:pk>/leer/", views.notification_read, name="notification_read"),
    path("notificaciones/leer-todas/", views.notifications_read_all, name="notifications_read_all"),
    path("configuracion/", views.social_settings, name="settings"),
]
