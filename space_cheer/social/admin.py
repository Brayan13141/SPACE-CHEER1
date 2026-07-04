from django.contrib import admin

from social.models import Post, PostComment, PostImage, PostLike


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "text", "shared_post", "created_at")
    list_filter = ("created_at",)
    search_fields = ("text", "author__username")
    inlines = [PostImageInline]


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author", "text", "created_at")
    search_fields = ("text", "author__username")


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "user", "created_at")
