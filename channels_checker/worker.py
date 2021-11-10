import json
import cfscrape
from slack_bolt import App
from slack_sdk.errors import SlackApiError
from slack_core import constants
from flask import Blueprint
from znatok_helper_api import watch, get_list

slack_bot = App(token=constants.CHECKER_SLACK_BOT_TOKEN, signing_secret=constants.CHECKER_SLACK_SIGNING_SECRET)
scraper = cfscrape.create_scraper()
channels_checker_blueprint = Blueprint('channels_checker_blueprint', __name__)

def get_messages():
  stack = []
  start = 1
  limit = 50
  while True:
    tasks, start, limit = get_list(start, limit)
    stack += tasks
    if start is None or limit is None:
      break
  return stack

def get_brainly_data(msgs):
  query = ''
  for msg in msgs:
    q = f"task{msg['taskId']}: questionById(id: {int(msg['taskId'])}) " + "{ canBeAnswered databaseId answers { hasVerified nodes {id isConfirmed} } } "
    query += q
 
  brainly_data = scraper.post(
    url = 'https://znanija.com/graphql/ru', 
    data = json.dumps({ 'query': '{ ' + query + '}' }),
    headers = { 'content-type': 'application/json; charset=utf-8' }
  )
  if brainly_data.status_code == 403:
    print('Blocked! 403 forbidden')
    return { 'data': None }

  return brainly_data.json()

@channels_checker_blueprint.route('/check-slack-channels', methods=['GET'])
def main():
  slack_messages = get_messages()
  if len(slack_messages) < 1: return

  brainly_data = get_brainly_data(slack_messages)['data']
  if brainly_data is None: return 'Brainly error! 403 Forbidden'

  for k in brainly_data.keys():
    task = brainly_data[k]
    if task is None: continue

    slack_message = None
    for slack_msg in slack_messages:
      if slack_msg['taskId'] == task['databaseId']: slack_message = slack_msg
    if slack_message is None: continue
  
    # contains verified answers -> delete
    if task['answers']['hasVerified'] == True:
      verified_answers = []
      for answer in task['answers']['nodes']:
        if answer['isConfirmed'] == True: verified_answers.append(answer)
    
      if len(task['answers']['nodes']) == len(verified_answers):
        print(f"Contains verified -> https://znanija.com/task/{task['databaseId']}")

        watch(f'https://znanija.com/task/{task["databaseId"]}', activity='end')
        try:
          slack_bot.client.chat_delete(
            channel = slack_message['channel'],
            ts = slack_message['ts'],
            token = constants.CHECKER_SLACK_ADMIN_TOKEN
          )
        except SlackApiError:
          print(f"Answer not found -> https://znanija.com/task/{task['databaseId']}")
          continue

    # answer has been deleted
    if len(task['answers']['nodes']) == 0:
      print(f"No answers -> https://znanija.com/task/{task['databaseId']}")
      watch(
        link=f'https://znanija.com/task/{task["databaseId"]}',
        channel=slack_message['channel'],
        ts=slack_message['ts'],
        status='no_answers',
        activity='start'
      )
      try:
        slack_bot.client.reactions_add(
          channel = slack_message['channel'],
          timestamp = slack_message['ts'],
          name = 'lower_left_ballpoint_pen'
        )
      except Exception:
        break
  return 'Executed'
