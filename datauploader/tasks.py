"""
Asynchronous tasks that update data in Open Humans.
These tasks:
  1. delete any current files in OH if they match the planned upload filename
  2. adds a data file
"""
import logging
import json
import tempfile
import requests
import os
from celery import shared_task
from django.conf import settings
from open_humans.models import OpenHumansMember
from datetime import datetime, timedelta
from demotemplate.settings import rr
from requests_respectful import RequestsRespectfulRateLimitedError
from ohapi import api
import arrow

# Set up logging.
logger = logging.getLogger(__name__)

TWITTER_GRAPHQL_BASE = 'https://api.twitter.com/graphql'
TWITTER_API_BASE = 'https://api.twitter.com'

@shared_task
def process_twitter(oh_id):
    """
    Update the twitter file for a given OH user
    """
    logger.debug('Starting twitter processing for {}'.format(oh_id))
    oh_member = OpenHumansMember.objects.get(oh_id=oh_id)
    oh_access_token = oh_member.get_access_token(
                            client_id=settings.OPENHUMANS_CLIENT_ID,
                            client_secret=settings.OPENHUMANS_CLIENT_SECRET)
    twitter_data = get_existing_twitter(oh_access_token)
    twitter_member = oh_member.datasourcemember
    twitter_access_token = twitter_member.get_access_token(
                            client_id=settings.TWITTER_CLIENT_ID,
                            client_secret=settings.TWITTER_CLIENT_SECRET)

    update_twitter(oh_member, twitter_access_token, twitter_data)


def update_twitter(oh_member, twitter_access_token, twitter_data):
    print(twitter_data)
    try: 
        start_date_iso = arrow.get(get_start_date(twitter_data, twitter_access_token)).datetime.isocalendar()
        print(start_date_iso)
        print(type(start_date_iso))
        twitter_data = remove_partial_data(twitter_data, start_date_iso)
        stop_date_iso = (datetime.utcnow()
                         + timedelta(days=7)).isocalendar()
        # while start_date_iso != stop_date_iso:
        print(f'processing {oh_member.oh_id}-{oh_member.oh_id} for member {oh_member.oh_id}')
        query = """ 
          {
           graphQLHub
           twitter {
           viewer{
           created_at
           description
           id
           screen_name
           name
           profile_image_url
           url
           tweets_count
           followers_count
            }    
          }
        } 
        """
        # Construct the authorization headers for twitter
        auth_string = "Bearer " + twitter_access_token 
        auth_header = {"Authorization": auth_string}
        # Make the request via POST, add query string & auth headers
        response = rr.post(TWITTER_GRAPHQL_BASE, json={'query': query}, headers=auth_header, realms=['twitter'])
        # Debug print
        # response.json())
        
        twitter_data = response.json()

        print(twitter_data)
        
        print('successfully finished update for {}'.format(oh_member.oh_id))
        twitter_member = oh_member.datasourcemember
        twitter_member.last_updated = arrow.now().format()
        twitter_member.save()
    except RequestsRespectfulRateLimitedError:
        logger.debug(
            'requeued processing for {} with 60 secs delay'.format(
                oh_member.oh_id)
                )
        process_twitter.apply_async(args=[oh_member.oh_id], countdown=61)  
    finally:
        replace_twitter(oh_member, twitter_data)


def replace_twitter(oh_member, twitter_data):
    # delete old file and upload new to open humans
    tmp_directory = tempfile.mkdtemp()
    metadata = {
        'description':
        'Twitter activity feed, repository contents and stars data.',
        'tags': ['demo', 'Twitter', 'test'],
        'updated_at': str(datetime.utcnow()),
        }
    out_file = os.path.join(tmp_directory, 'twitter-data.json')
    logger.debug('deleted old file for {}'.format(oh_member.oh_id))
    api.delete_file(oh_member.access_token,
                    oh_member.oh_id,
                    file_basename="twitter-data.json")
    with open(out_file, 'w') as json_file:
        json.dump(twitter_data, json_file)
        json_file.flush()
    api.upload_aws(out_file, metadata,
                   oh_member.access_token,
                   project_member_id=oh_member.oh_id)
    logger.debug('uploaded new file for {}'.format(oh_member.oh_id))


def remove_partial_data(twitter_data, start_date):
    remove_indexes = []
    for i, element in enumerate(twitter_data):
        element_date = datetime.strptime(
                                element['date'], "%Y%m%d").isocalendar()[:2]
        if element_date == start_date:
            remove_indexes.append(i)
    for index in sorted(remove_indexes, reverse=True):
        del twitter_data[index]
    return twitter_data


def get_start_date(twitter_data, twitter_access_token):
    if not twitter_data:
        url = TWITTER_API_BASE + "/user?access_token={}".format(
                                        twitter_access_token
        )
        response = rr.get(url, wait=True, realms=['twitter'])
        reso = response.json()
        print(reso)
        return reso['created_at']
    else:
        return twitter_data[-1]['date']


def get_existing_twitter(oh_access_token):
    member = api.exchange_oauth2_member(oh_access_token)
    for dfile in member['data']:
        if 'Twitter' in dfile['metadata']['tags']:
            # get file here and read the json into memory
            tf_in = tempfile.NamedTemporaryFile(suffix='.json')
            tf_in.write(requests.get(dfile['download_url']).content)
            tf_in.flush()
            twitter_data = json.load(open(tf_in.name))
            return twitter_data
    return []
