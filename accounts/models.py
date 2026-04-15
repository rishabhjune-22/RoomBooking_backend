from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(unique=True)

    encrypted_dek = models.TextField(blank=True, null=True)
    dek_wrap_nonce = models.TextField(blank=True, null=True)
    kdf_metadata = models.JSONField(blank=True, null=True)

    def __str__(self):
        return self.username