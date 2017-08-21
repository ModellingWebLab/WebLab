from django.contrib.auth import login
from django.core.urlresolvers import reverse
from django.views.generic.edit import FormView, UpdateView

from .forms import MyAccountForm, RegistrationForm


class RegistrationView(FormView):
    form_class = RegistrationForm
    template_name = 'registration/register.html'
    success_url = '/'

    class Meta:
        fields = ('username', 'email', 'full_name', 'institution')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)


class MyAccountView(UpdateView):
    form_class = MyAccountForm
    template_name = 'registration/myaccount.html'

    def get_object(self):
        return self.request.user

    def get_success_url(self):
        return reverse('accounts:myaccount')
