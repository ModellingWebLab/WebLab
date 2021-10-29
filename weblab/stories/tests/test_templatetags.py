import pytest

import stories.templatetags.stories as story_tags
from core import recipes


#can_delete_story
#can_manage_story
@pytest.mark.django_db
def test_can_delete_story(story, other_user, admin_user):
    context = {'user': story.author}
    assert story_tags.can_delete_story(context, story)

    context = {'user': other_user}
    assert not story_tags.can_delete_story(context, story)

    story.add_collaborator(context['user'])
    assert not story_tags.can_delete_story(context, story)

    context = {'user': admin_user}
    assert story_tags.can_delete_story(context, story)

@pytest.mark.django_db
def test_can_manage_story(story, other_user):
    context = {'user': story.author}
    assert story_tags.can_manage_story(context, story)

    context = {'user': other_user}
    assert not story_tags.can_manage_story(context, story)

    story.add_collaborator(context['user'])
    assert not story_tags.can_manage_story(context, story)

    context = {'user': admin_user}
    assert story_tags.can_manage_story(context, story)

