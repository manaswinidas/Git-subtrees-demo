from ohapi import api
from django.conf import settings
import arrow
from datetime import timedelta


def get_github_file(oh_member):
    try:
        oh_access_token = oh_member.get_access_token(
                                client_id=settings.OPENHUMANS_CLIENT_ID,
                                client_secret=settings.OPENHUMANS_CLIENT_SECRET)
        user_object = api.exchange_oauth2_member(oh_access_token)
        for dfile in user_object['data']:
            if 'Github' in dfile['metadata']['tags']:
                return dfile['download_url']
        return ''

    except:
        return 'error'


def check_update(github_member):
    if github_member.last_submitted < (arrow.now() - timedelta(hours=1)):
        return True
    return False
