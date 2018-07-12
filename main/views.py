import logging
import requests
from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.conf import settings
from open_humans.models import OpenHumansMember
from .models import DataSourceMember
from .helpers import get_github_file, check_update
from datauploader.tasks import process_github
from ohapi import api
import arrow

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
            github_url = ('https://github.com/login/oauth/authorize?'
                         'response_type=code&scope=activity location&'
                         'redirect_uri={}&client_id={}').format(
                            settings.GITHUB_REDIRECT_URI,
                            settings.GITHUB_CLIENT_ID)
            logger.debug(github_url)
            context['github_url'] = github_url
            return render(request, 'main/complete.html',
                          context=context)
        return redirect("/dashboard")

    logger.debug('Invalid code exchange. User returned to starting page.')
    return redirect('/')


def dashboard(request):
    if request.user.is_authenticated:
        if hasattr(request.user.oh_member, 'datasourcemember'):
            github_member = request.user.oh_member.datasourcemember
            download_file = get_github_file(request.user.oh_member)
            if download_file == 'error':
                logout(request)
                return redirect("/")
            connect_url = ''
            # allow_update = check_update(github_member)
            allow_update = True
        else:
            allow_update = False
            github_member = ''
            download_file = ''
            connect_url = ('https://github.com/login/oauth/authorize?'
                           'response_type=code&scope=activity location&'
                           'redirect_uri={}&client_id={}').format(
                            settings.GITHUB_REDIRECT_URI,
                            settings.GITHUB_CLIENT_ID)
      
        context = {
            'oh_member': request.user.oh_member,
            'github_member': github_member,
            'download_file': download_file,
            'connect_url': connect_url,
            'allow_update': allow_update
        }
        return render(request, 'main/dashboard.html',
                      context=context)
    return redirect("/")


def remove_github(request):
    if request.method == "POST" and request.user.is_authenticated:
        try:
            oh_member = request.user.oh_member
            api.delete_file(oh_member.access_token,
                            oh_member.oh_id,
                            file_basename="github-data.json")
            messages.info(request, "Your Github account has been removed")
            github_account = request.user.oh_member.datasourcemember
            github_account.delete()
        except:
            github_account = request.user.oh_member.datasourcemember
            github_account.delete()
            messages.info(request, ("Something went wrong, please"
                          "re-authorize us on Open Humans"))
            logout(request)
            return redirect('/')
    return redirect('/dashboard')


def update_data(request):
    if request.method == "POST" and request.user.is_authenticated:
        oh_member = request.user.oh_member
        process_github.delay(oh_member.oh_id)
        github_member = oh_member.datasourcemember
        github_member.last_submitted = arrow.now().format()
        github_member.save()
        messages.info(request,
                      ("An update of your Github data has been started! "
                       "It can take some minutes before the first data is "
                       "available. Reload this page in a while to find your "
                       "data"))
        return redirect('/dashboard')


def github_complete(request):
    """
    Receive user from Github source. Store data, start processing.
    """
    logger.debug("Received user returning from Github.")
    # Exchange code for token.
    # This creates an OpenHumansMember and associated user account.
    code = request.GET.get('code', '')
    ohmember = request.user.oh_member
    github_member = github_code_to_member(code=code, ohmember=ohmember)

    if github_member:
        messages.info(request, "Your Github account has been connected")
        # process_github.delay(ohmember.oh_id)
        return redirect('/dashboard')

    logger.debug('Invalid code exchange. User returned to starting page.')
    messages.info(request, ("Something went wrong, please try connecting your "
                            "Github account again"))
    return redirect('/dashboard')


def github_code_to_member(code, ohmember):
    """
    Exchange code for token, use this to create and return Github members.
    If a matching github exists, update and return it.
    """
    print("FOOBAR.")
    if settings.GITHUB_CLIENT_SECRET and \
       settings.GITHUB_CLIENT_ID and code:
        data = {
            'grant_type': 'authorization_code',
            'redirect_uri': settings.GITHUB_REDIRECT_URI,
            'code': code,
            'client_id': settings.GITHUB_CLIENT_ID,
            'client_secret': settings.GITHUB_CLIENT_SECRET
        }
        # Add headers telling Github's API that we want a JSON response (instead of plaintext)
        headers = {'Accept': 'application/json'}
        # Get the access_token from the code
        req = requests.post('https://github.com/login/oauth/access_token',
                            data=data, headers=headers)
        data = req.json()
        print(data)
        # Now that we have a token, let's get the users "profile" back with their token:
        auth_string = 'token {}'.format(data['access_token'])
        token_header = {'Authorization': auth_string}
        user_data_r = requests.get('https://api.github.com/user', headers=token_header)
        user_data = user_data_r.json()
        print(user_data)
        if 'access_token' in data:
            try:
                github_member = DataSourceMember.objects.get(
                    github_id=user_data['id'])
                logger.debug('Member {} re-authorized.'.format(
                    github_member.github_id))
                github_member.access_token = data['access_token']
                print('got old github member')
            except DataSourceMember.DoesNotExist:
                github_member = DataSourceMember(
                    github_id=user_data['id'],
                    access_token=data['access_token'])
                github_member.user = ohmember
                logger.debug('Member {} created.'.format(data['access_token']))
                print('make new github member')
            github_member.save()

            return github_member

        elif 'error' in req.json():
            logger.debug('Error in token exchange: {}'.format(req.json()))
        else:
            logger.warning('Neither token nor error info in Github response!')
    else:
        logger.error('GITHUB_CLIENT_SECRET or code are unavailable')
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
    return None
