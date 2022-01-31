from slack_sdk.errors import SlackApiError
from slack_sdk.web import WebClient

from slack_core import constants, utils


def app_home_opened(event_data):
    bot = WebClient(constants.SLACK_OAUTH_TOKEN_BOT)
    home_form = utils.get_view('files/app_home/app_home.json')

    try:
        bot.views_publish(user_id=event_data['event']['user'], view=home_form, hash=event_data['event']['view']['hash'] if 'view' in event_data['event'] else None)
    except SlackApiError:
        pass
