from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models

class UserManager(BaseUserManager):
    def create_user(self, kakao_id, nickname,  **extra_fields):
        if not kakao_id:
            raise ValueError("Kakao ID is required")
        user = self.model(kakao_id=kakao_id, nickname=nickname, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

class User(AbstractBaseUser):
    kakao_id = models.CharField(max_length=100, unique=True)
    nickname = models.CharField(max_length=100)
    profile_image_url = models.URLField(max_length=200, null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'kakao_id'
    REQUIRED_FIELDS = ['nickname']

    def __str__(self):
        return self.nickname
