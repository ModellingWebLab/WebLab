from django.conf import settings
from django.db import models, transaction

from core import visibility
from entities.models import ModelEntity, ProtocolEntity


class ExperimentManager(models.Manager):
    @transaction.atomic
    def submit_experiment(self, model, protocol, user):

        experiment, _ = Experiment.objects.get_or_create(
            model=model,
            protocol=protocol,
            defaults={
                'author': user,
                'visibility': visibility.get_joint_visibility(model.visibility, protocol.visibility)
            }
        )

        return experiment


class Experiment(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL)
    visibility = models.CharField(
        max_length=16,
        choices=visibility.CHOICES,
        help_text=visibility.HELP_TEXT.replace('\n', '<br />'),
    )

    model = models.ForeignKey(ModelEntity, related_name='model_experiments')
    protocol = models.ForeignKey(ProtocolEntity, related_name='protocol_experiments')

    objects = ExperimentManager()

    class Meta:
        unique_together = ('model', 'protocol')
        verbose_name_plural = 'Experiments'

        permissions = (
            ('create_experiment', 'Can create experiments'),
        )

    @property
    def name(self):
        return '%s / %s' % (self.model.name, self.protocol.name)
