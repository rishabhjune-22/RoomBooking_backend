from django.urls import path
from .views import signup, logout, encryption_material
urlpatterns = [
    path('signup/', signup),
    path('logout/', logout, name='logout'),
    path("encryption-material/", encryption_material, name="encryption_material"),
]