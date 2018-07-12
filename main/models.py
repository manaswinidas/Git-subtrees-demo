from django.db import models
from django.conf import settings
from open_humans.models import OpenHumansMember
from datetime import timedelta
import arrow
import requests


class DataSourceMember(models.Model):
    """
    Store OAuth data for a data source.
    This is a one to one relationship with a OpenHumansMember model
    You can find the OpenHumansMember model in open_humans/models.py

    There is a bi-directional link, called oh_member from this object. This could be used
    to fetch the OpenHumansMember object given a DataSourceMember object.
    """
    user = models.OneToOneField(OpenHumansMember, on_delete=models.CASCADE)
    # Your other fields should go below here
    github_id = models.CharField(max_length=255, unique=True, null=True)
    access_token = models.CharField(max_length=512, null=True)

    scope = models.CharField(max_length=512, null=True)
    token_type = models.CharField(max_length=512, null=True)

    last_updated = models.DateTimeField(
                            default=(arrow.now() - timedelta(days=7)).format())
    last_submitted = models.DateTimeField(
                            default=(arrow.now() - timedelta(days=7)).format())
    # token_expires = models.DateTimeField(default=arrow.now().format())

    @staticmethod
    def get_expiration(expires_in):
        return (arrow.now() + timedelta(seconds=expires_in)).format()

    def get_access_token(self,
                         client_id=settings.GITHUB_CLIENT_ID,
                         client_secret=settings.GITHUB_CLIENT_SECRET):
        """
        Return access token. Refresh first if necessary.
        """
        # Also refresh if nearly expired (less than 60s remaining).
        # delta = timedelta(seconds=60)
        # if arrow.get(self.token_expires) - delta < arrow.now():
        #     self._refresh_tokens(client_id=client_id,
        #                          client_secret=client_secret)
        return self.access_token

    # def _refresh_tokens(self, client_id, client_secret):
    #     """
    #     Refresh access token.
    #     """
    #     response = requests.post(
    #         'https://api.github.com/login/oauth/access_token?',
    #         data={
    #             'grant_type': 'refresh_token',
    #             'refresh_token': self.refresh_token,
    #             'client_id': client_id,
    #             'client_secret': client_secret},
    #         auth=requests.auth.HTTPBasicAuth(client_id, client_secret))
    #     if response.status_code == 200:
    #         data = response.json()
    #         self.github_id = data['user_id']
    #         self.access_token = data['access_token']
    #         self.refresh_token = data['refresh_token']
    #         self.token_expires = self.get_expiration(data['expires_in'])
    #         self.save()