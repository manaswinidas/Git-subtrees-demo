import logging
import requests
from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.conf import settings
from open_humans.models import OpenHumansMember
from .models import DataSourceMember
from .helpers import get_twitter_file, check_update
from datauploader.tasks import process_twitter
from ohapi import api
import arrow
import tweepy

# Set up logging.
logger = logging.getLogger(__name__)


def index(request):
    """
    Starting page for app.
    """
    if request.user.is_authenticated:
        return redirect('/dashboard')
    else:
        context = {'client_id': settings.OPENHUMANS_CLIENT_ID,
                #    'redirect_uri': '{}/complete'.format(settings.OPENHUMANS_APP_BASE_URL),
                   'oh_proj_page': settings.OH_ACTIVITY_PAGE}

        return render(request, 'main/index.html', context=context)


def complete(request):
    """
    Receive user from Open Humans. Store data, start upload.
    """
    print("Received user returning from Open Humans.")
    # Exchange code for token.
    # This creates an OpenHumansMember and associated user account.
    code = request.GET.get('code', '')
    oh_member = oh_code_to_member(code=code)

    if oh_member:
        # Log in the user.
        user = oh_member.user
        login(request, user,
              backend='django.contrib.auth.backends.ModelBackend')

        # Initiate a data transfer task, then render `complete.html`.
        # xfer_to_open_humans.delay(oh_id=oh_member.oh_id)
        context = {'oh_id': oh_member.oh_id,
                   'oh_proj_page': settings.OH_ACTIVITY_PAGE}
        if not hasattr(oh_member, 'datasourcemember'):
            # Use tweepy to set up auth handler
            auth = tweepy.OAuthHandler(settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET, settings.TWITTER_REDIRECT_URI)
            redirect_url = ''
            try:
                redirect_url = auth.get_authorization_url()
                request.session['request_token'] = auth.request_token
                print(redirect_url)
            except tweepy.TweepError:
                print('Error! Failed to get request token.')

            context['twitter_url'] = redirect_url
            return render(request, 'main/complete.html',
                          context=context)
        return redirect("/dashboard")

    logger.debug('Invalid code exchange. User returned to starting page.')
    return redirect('/')


def dashboard(request):
    if request.user.is_authenticated:
        if hasattr(request.user.oh_member, 'datasourcemember'):
            twitter_member = request.user.oh_member.datasourcemember
            download_file = get_twitter_file(request.user.oh_member)
            if download_file == 'error':
                logout(request)
                return redirect("/")
            redirect_url = ''
            # allow_update = check_update(twitter_member)
            allow_update = True
        else:
            allow_update = False
            twitter_member = ''
            download_file = ''

            # Use tweepy to set up auth handler
            auth = tweepy.OAuthHandler(settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET, settings.TWITTER_REDIRECT_URI)
            redirect_url = ''
            try:
                redirect_url = auth.get_authorization_url()
                request.session['request_token'] = auth.request_token
                print(redirect_url)
                print(request.session['request_token'])
            except tweepy.TweepError:
                print('Error! Failed to get request token.')

            # connect_url = redirect_url
      
        context = {
            'oh_member': request.user.oh_member,
            'twitter_member': twitter_member,
            'download_file': download_file,
            'connect_url': redirect_url,
            'allow_update': allow_update
        }
        return render(request, 'main/dashboard.html',
                      context=context)
    return redirect("/")


def remove_twitter(request):
    if request.method == "POST" and request.user.is_authenticated:
        try:
            oh_member = request.user.oh_member
            api.delete_file(oh_member.access_token,
                            oh_member.oh_id,
                            file_basename="twitter-data.json")
            messages.info(request, "Your Twitter account has been removed")
            twitter_account = request.user.oh_member.datasourcemember
            twitter_account.delete()
        except:
            twitter_account = request.user.oh_member.datasourcemember
            twitter_account.delete()
            messages.info(request, ("Something went wrong, please"
                          "re-authorize us on Open Humans"))
            logout(request)
            return redirect('/')
    return redirect('/dashboard')


def update_data(request):
    if request.method == "POST" and request.user.is_authenticated:
        oh_member = request.user.oh_member
        process_twitter.delay(oh_member.oh_id)
        twitter_member = oh_member.datasourcemember
        twitter_member.last_submitted = arrow.now().format()
        twitter_member.save()
        messages.info(request,
                      ("An update of your Twitter data has been started! "
                       "It can take some minutes before the first data is "
                       "available. Reload this page in a while to find your "
                       "data"))
        return redirect('/dashboard')


def twitter_complete(request):
    """
    Receive user from Twitter source. Store data, start processing.
    """
    logger.debug("Received user returning from Twitter.")
    # Exchange code for token.
    # This creates an OpenHumansMember and associated user account.
    oauth_verifier = request.GET.get('oauth_verifier', '')
    ohmember = request.user.oh_member
    twitter_member = twitter_code_to_member(oauth_verifier=oauth_verifier, ohmember=ohmember, request=request)

    if twitter_member:
        messages.info(request, "Your Twitter account has been connected")
        process_twitter.delay(ohmember.oh_id)
        return redirect('/dashboard')

    logger.debug('Invalid code exchange. User returned to starting page.')
    messages.info(request, ("Something went wrong, please try connecting your "
                            "Twitter account again"))
    return redirect('/dashboard')


def twitter_code_to_member(oauth_verifier, ohmember, request):
    """
    Exchange code for token, use this to create and return Twitter members.
    If a matching twitter exists, update and return it.
    """
    if settings.TWITTER_CLIENT_SECRET and \
       settings.TWITTER_CLIENT_ID and oauth_verifier:

        # Attempt to get access token
        auth = tweepy.OAuthHandler(settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET, settings.TWITTER_REDIRECT_URI)
        auth.request_token = request.session['request_token']
        del request.session['request_token']

        try:
            auth.get_access_token(oauth_verifier)
            print(auth.username)
            print(auth.access_token)
            print(auth.access_token_secret)
        except tweepy.TweepError:
            print('Error! Failed to get access token.')

        # Now that we have a token, let's get the users "profile" back with their token:
        api = tweepy.API(auth)
        user_data = api.verify_credentials()
        print(user_data)
        print(user_data.screen_name)
        # auth_string = 'token {}'.format(data['access_token'])
        # token_header = {'Authorization': auth_string}
        # user_data_r = requests.get('https://api.twitter.com/users', headers=token_header)
        # user_data = user_data_r.json()
        # print(user_data)
        if auth.access_token:
            try:
                twitter_member = DataSourceMember.objects.get(
                    twitter_id=user_data.screen_name)
                logger.debug('Member {} re-authorized.'.format(
                    twitter_member.twitter_id))
                twitter_member.access_token = auth.access_token
                twitter_member.access_token_secret = auth.access_token_secret
                print('got old twitter member')
            except DataSourceMember.DoesNotExist:
                twitter_member = DataSourceMember(
                    twitter_id=user_data.screen_name,
                    access_token=auth.access_token,
                    access_token_secret = auth.access_token_secret)
                twitter_member.user = ohmember
                logger.debug('Member {} created.'.format(auth.access_token))
                print('make new twitter member')
            twitter_member.save()

            return twitter_member
            # print("access token is there")
            # return None

        elif 'error' in req.json():
            logger.debug('Error in token exchange: {}'.format(req.json()))
        else:
            logger.warning('Neither token nor error info in Twitter response!')
    else:
        logger.error('TWITTER_CLIENT_SECRET or code are unavailable')
    return None


def oh_code_to_member(code):
    """
    Exchange code for token, use this to create and return OpenHumansMember.
    If a matching OpenHumansMember exists, update and return it.
    """
    if settings.OPENHUMANS_CLIENT_SECRET and \
       settings.OPENHUMANS_CLIENT_ID and code:
        data = {
            'grant_type': 'authorization_code',
            'redirect_uri':
            '{}/complete'.format(settings.OPENHUMANS_APP_BASE_URL),
            'code': code,
        }
        req = requests.post(
            '{}/oauth2/token/'.format(settings.OPENHUMANS_OH_BASE_URL),
            data=data,
            auth=requests.auth.HTTPBasicAuth(
                settings.OPENHUMANS_CLIENT_ID,
                settings.OPENHUMANS_CLIENT_SECRET
            )
        )
        data = req.json()

        if 'access_token' in data:
            oh_id = oh_get_member_data(
                data['access_token'])['project_member_id']
            try:
                oh_member = OpenHumansMember.objects.get(oh_id=oh_id)
                logger.debug('Member {} re-authorized.'.format(oh_id))
                oh_member.access_token = data['access_token']
                oh_member.refresh_token = data['refresh_token']
                oh_member.token_expires = OpenHumansMember.get_expiration(
                    data['expires_in'])
            except OpenHumansMember.DoesNotExist:
                oh_member = OpenHumansMember.create(
                    oh_id=oh_id,
                    access_token=data['access_token'],
                    refresh_token=data['refresh_token'],
                    expires_in=data['expires_in'])
                logger.debug('Member {} created.'.format(oh_id))
            oh_member.save()

            return oh_member

        elif 'error' in req.json():
            logger.debug('Error in token exchange: {}'.format(req.json()))
        else:
            logger.warning('Neither token nor error info in OH response!')
    else:
        logger.error('OH_CLIENT_SECRET or code are unavailable')
    return None


def oh_get_member_data(token):
    """
    Exchange OAuth2 token for member data.
    """
    req = requests.get(
        '{}/api/direct-sharing/project/exchange-member/'
        .format(settings.OPENHUMANS_OH_BASE_URL),
        params={'access_token': token}
        )
    if req.status_code == 200:
        return req.json()
    raise Exception('Status code {}'.format(req.status_code))
    # return None
