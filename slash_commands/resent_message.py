from main_file import app
from flask import request, make_response
from slack import WebClient
import constants
from functions_slack import ephemeral_message
from tasks import async_task


@app.route('/resent_messages', methods=["POST"])
def resent_messages():
    if not request:
        return make_response('', 404)
    resent_messages_background(request['channel_id'])
    return make_response('', 200)


@async_task
def resent_messages_background(channel_id):
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN_TEST)
    channel_history = client.channels_history(channel=channel_id)
    if not channel_history['ok']:
        ephemeral_message('Не получилось получить список сообщений')
        return
    messages_with_pen = [message_with_reactions for message_with_reactions in
                         [message for message in channel_history['messages'] if 'reactions' in message.keys()]
                         if 'lower_left_ballpoint_pen' in
                         [reaction['name'] for reaction in message_with_reactions['reactions']]]
    # with open()
    # message_with_empty_answer = [message for message in messages_with_pen if requests.get()]