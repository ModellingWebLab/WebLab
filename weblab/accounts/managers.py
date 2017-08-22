from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, username, email, full_name, institution='', password=None):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.model(
            username=username,
            email=self.normalize_email(email),
            full_name=full_name,
            institution=institution,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, full_name, institution, password):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.create_user(
            username,
            password=password,
            email=email,
            full_name=full_name,
            institution=institution,
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user
