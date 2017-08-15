from django.contrib.auth import login
from django.views.generic.edit import FormView

from .forms import RegistrationForm


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
