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
]
