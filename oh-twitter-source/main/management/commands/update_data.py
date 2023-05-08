from django.core.management.base import BaseCommand
from main.models import DataSourceMember
from datauploader.tasks import process_twitter
import arrow
from datetime import timedelta


class Command(BaseCommand):
    help = 'Updates data for all members'

    def handle(self, *args, **options):
        users = DataSourceMember.objects.all()
        for twitter_user in users:
            if twitter_user.last_updated < (arrow.now() - timedelta(days=4)):
                oh_id = twitter_user.user.oh_id
                process_twitter.delay(oh_id)
            else:
                print("didn't update {}".format(twitter_user.moves_id))