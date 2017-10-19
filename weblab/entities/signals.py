
def entity_created(sender, instance, created, **kwargs):
    if created:
        instance.init_repo()
