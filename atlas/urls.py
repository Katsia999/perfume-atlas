from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from catalog import views

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search_page, name="search"),
    path("fragrances/", views.catalog_page, name="catalog"),
    path("fragrances/<int:pk>/", views.fragrance_detail, name="fragrance-detail"),
    path("selection/", views.selection_page, name="selection"),
    path("materials/<int:pk>/", views.material_detail, name="material-detail"),
    path("admin/", admin.site.urls),
]

urlpatterns += static(
    settings.LOCAL_BOTTLE_PHOTO_URL, document_root=settings.LOCAL_BOTTLE_PHOTO_ROOT
)
