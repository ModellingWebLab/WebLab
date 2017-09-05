
def test_my_account_view_requires_login(client):
    response = client.get('/accounts/myaccount/')
    assert response.status_code == 302
    assert '/login/' in response.url
