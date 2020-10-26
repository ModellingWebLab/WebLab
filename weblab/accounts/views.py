from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.views.generic.edit import FormView, UpdateView

from .forms import MyAccountForm, RegistrationForm


class RegistrationView(FormView):
    form_class = RegistrationForm
    template_name = 'registration/register.html'
    success_url = '/'

    class Meta:
        fields = ('email', 'full_name', 'institution')

    def form_valid(self, form):
        user = form.save()
        login(
            self.request,
            user,
            backend='django.contrib.auth.backends.ModelBackend',
        )
        return super().form_valid(form)


class MyAccountView(LoginRequiredMixin, UpdateView):
    form_class = MyAccountForm
    template_name = 'registration/myaccount.html'

    def get_object(self):
        return self.request.user

    def get_success_url(self):
        return reverse('accounts:myaccount')

    def get_context_data(self, **kwargs):
        perms = {
            'entities.create_fittingspec',
            'entities.create_protocol',
            'entities.create_model',
        }

        codes = self.get_object().get_all_permissions() & perms
        code_names = {code.split('.')[-1] for code in codes}

        user_perms = Permission.objects.filter(codename__in=code_names)

        kwargs.update(**{
            'user_permissions': user_perms,
        })
        return super().get_context_data(**kwargs)
