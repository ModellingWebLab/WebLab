import pytest

from core import recipes


@pytest.mark.django_db
class TestTransferOwner:
    def test_fittingspec_transfer_success(self, client, logged_in_user, other_user, helpers):
        helpers.add_permission(logged_in_user, 'create_fittingspec')
        fittingspec = recipes.fittingspec.make(author=logged_in_user)
        oldpath = fittingspec.repo_abs_path

        assert fittingspec.author.email == 'test@example.com'
        response = client.post(
            '/fitting/specs/%d/transfer' % fittingspec.pk,
            data={
                'email': other_user.email,
            },
        )
        assert response.status_code == 302
        fittingspec.refresh_from_db()
        assert fittingspec.author == other_user
        assert not oldpath.exists()
        assert fittingspec.repo_abs_path.exists()
