from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    def admins(self):
        return self.filter(is_superuser=True)

    def create_user(self, email, full_name, institution='', password=None):
        """
        Creates and saves a user with the given details and password.
        """
        user = self.model(
            email=self.normalize_email(email),
            full_name=full_name,
            institution=institution,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, institution, password):
        """
        Creates and saves a superuser with the given details and password.
        """
        user = self.create_user(
            email,
            password=password,
            full_name=full_name,
            institution=institution,
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user
