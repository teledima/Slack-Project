import re
import json
from slack_sdk import WebClient
from slack_sdk.models.blocks import *

from slack_core import constants, utils, async_task, settings_collection, smiles_collection


def open_update_smile_view(payload):
    current_user_id = payload['user']['id']

    bot = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    update_smile_view = utils.get_view('files/app_home/update_smile_modal.json')
    current_user_settings = settings_collection.document(current_user_id).get()

    search_result = smiles_collection.where('user_id', '==', current_user_id).get()
    current_smile = {'id': search_result[0].id, 'user_id': search_result[0].get('user_id')} if search_result else None

    if utils.is_admin(payload['user']['id']):
        update_smile_view['blocks'].append(
            ActionsBlock(
                block_id='user_select_block',
                elements=[UserSelectElement(placeholder='Выберите пользователя', action_id='user_select_action')]
            ).to_dict()
        )

    if not current_smile:
        description_text = 'У вас ещё нет смайлика. Добавьте его, чтобы отмечать свои ответы.'
    elif current_smile:
        description_text = f'Ваш смайлик :{current_smile["id"]}:'

    update_smile_view['blocks'].append(
        SectionBlock(block_id='description_block', text=MarkdownTextObject(text=description_text)).to_dict()
    )

    update_smile_view['blocks'].append(
        InputBlock(
            block_id='input_smile_block',
            element=PlainTextInputElement(action_id='input_smile_action', placeholder='Введите смайлик'),
            label='Смайлик',
            optional=True,
        ).to_dict()
    )
    send_notification_option = Option(
        value='send_notification',
        label='Отправлять уведомления',
        description='Когда под проверкой поставят :lower_left_ballpoint_pen: тогда <@U0184CFEU56> отправит сообщение об освободившемся поле для ответа'
    )
    update_smile_view['blocks'].append(
        ActionsBlock(
            elements=[
                CheckboxesElement(
                    action_id='settings_action',
                    options=[send_notification_option],
                    initial_options=[send_notification_option if current_user_settings.exists and current_user_settings.get('send_notification') else None]
                )
            ]
        ).to_dict()
    )

    bot.views_open(trigger_id=payload['trigger_id'], view=update_smile_view)


def update_smile_user_select(payload):
    def get_settings(user_id):
        info = dict(type='info', smile=dict(), settings=dict())
        search_result = smiles_collection.where('user_id', '==', user_id).get()
        settings_ref = settings_collection.document(user_id).get()
        if search_result:
            smile_info = search_result[0]
            info['smile'] = {'id': smile_info.id, 'user_id': user_id}
        else:
            info['smile'] = {'id': None, 'user_id': user_id}
        if settings_ref.exists:
            info['settings']['send_notification'] = settings_ref.get('send_notification')
        else:
            info['settings']['send_notification'] = False
        return info
    user_settings = get_settings(payload['actions'][0]['selected_user'])
    view = payload['view']

    bot = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    update_smile_view = utils.get_view('files/app_home/update_smile_modal.json')

    send_notification_option = Option(
        value='send_notification',
        label='Отправлять уведомления',
        description='Когда под проверкой поставят :lower_left_ballpoint_pen: тогда <@U0184CFEU56> отправит уведомление об освободившемся поле для ответа'
    ).to_dict()

    update_smile_view['submit']['text'] = 'Обновить настройки'
    for i, block in enumerate(view['blocks']):
        if block['block_id'] == 'description_block':
            if user_settings['smile']["id"]:
                block['text']['text'] = f'Смайлик <@{user_settings["smile"]["user_id"]}> :{user_settings["smile"]["id"]}:'
            else:
                block['text']['text'] = 'Смайлик не выбран'
        elif 'elements' in block and 'settings_action' in block['elements'][0]['action_id']:
            # to update the checkbox on the page, you need to regenerate the id
            block['block_id'] = utils.generate_random_id()
            if user_settings['settings']['send_notification']:
                block['elements'][0]['initial_options'] = [send_notification_option]
            elif block['elements'][0].get('initial_options'):
                block['elements'][0].pop('initial_options')

    update_smile_view['blocks'] = view['blocks']

    bot.views_update(view=update_smile_view, view_id=view['id'], hash=view['hash'])


def open_all_smiles(payload):
    open_list_smiles_view(start=0, end=constants.ALL_SMILES_PAGE_SIZE, admin=utils.is_admin(payload['user']['id']),
                          add_info={'trigger_id': payload['trigger_id']})


def all_smiles_next_page(payload):
    metadata = json.loads(payload['view']['private_metadata'])
    open_list_smiles_view(start=metadata['end_at'], end=metadata['end_at'] + constants.ALL_SMILES_PAGE_SIZE,
                          admin=utils.is_admin(payload['user']['id']),
                          update_info={'view_id': payload['view']['id'], 'hash': payload['view']['hash']})


def all_smiles_prev_page(payload):
    metadata = json.loads(payload['view']['private_metadata'])
    open_list_smiles_view(start=metadata['start_at'] - constants.ALL_SMILES_PAGE_SIZE, end=metadata['start_at'],
                          admin=utils.is_admin(payload['user']['id']),
                          update_info={'view_id': payload['view']['id'], 'hash': payload['view']['hash']})


def delete_smile(payload):
    smile_id = payload['actions'][0]['value']

    smiles_collection.document(smile_id).delete()

    metadata = json.loads(payload['view']['private_metadata'])
    open_list_smiles_view(start=metadata['start_at'], end=metadata['start_at'] + constants.ALL_SMILES_PAGE_SIZE,
                          admin=utils.is_admin(payload['user']['id']),
                          update_info={'view_id': payload['view']['id'], 'hash': payload['view']['hash']})


def submit_update_smile(payload, result):
    def update_smile():
        try:
            smile_id = list(filter(lambda item: item != '', smile_raw.split(':'))).pop()
            if re.search(r'[^a-z0-9-_]', smile_id):
                return dict(
                    input_smile_block='Название должно состоять из латинских строчных букв, цифр и не могут содержать пробелы, точки и большинство знаков препинания')
        except IndexError:
            return dict(input_smile_block='Смайлик введён в некорректном формате')
        # remove the ability to use this smile
        if smile_id == 'lower_left_ballpoint_pen':
            return dict(input_smile_block='Вы не можете выбрать этот смайлик')

        # get document by entered smiled_id
        doc_ref = smiles_collection.document(smile_id)

        # check that smile is available
        if not doc_ref.get().exists:
            # find old smile for user
            old_smile = smiles_collection.where('user_id', '==', user_id).get()
            if old_smile:
                # delete document by old smile
                old_smile[0].reference.delete()

            data = {'expert_name': username, 'user_id': user_id}

            # create new document
            doc_ref.set(data)
        elif doc_ref.get().get('user_id') != user_id:
            return dict(input_smile_block=f'{doc_ref.get().get("expert_name")} уже занял этот смайлик')
    state_values = payload['view']['state']['values']
    smile_raw = state_values['input_smile_block']['input_smile_action']['value']
    selected_options = [state_values[block]['settings_action']['selected_options']
                        for block in state_values if 'settings_action' in state_values[block]][0]

    send_notification = len(selected_options) > 0 and len(
        list(filter(lambda item: item['value'] == 'send_notification', selected_options))
    ) > 0

    if utils.is_admin(payload['user']['id']):
        user_id = payload['view']['state']['values']['user_select_block']['user_select_action']['selected_user']
    else:
        user_id = None

    user_id = user_id or payload['user']['id']

    if smile_raw:
        username = utils.get_username(user_id)
        change_errors = update_smile()
        if change_errors:
            result['response_action'] = 'errors'
            result['errors'] = change_errors

    if not result.get('errors'):
        settings_collection.document(user_id).set({'send_notification': send_notification}, merge=True)
        result['response_action'] = 'clear'


@async_task
def open_list_smiles_view(start, end, admin, add_info=None, update_info=None):
    assert add_info or update_info

    bot = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    all_smiles_view = utils.get_view('files/app_home/all_smiles_modal.json')
    # querying the database for the number of elements 1 more than the page size
    smiles_page_one_extra = [doc for doc in smiles_collection.order_by(field_path='expert_name').offset(start).limit(end - start + 1).get()]

    # check if the requested number is equal to the length of the array, then 1 additional element is discarded
    if len(smiles_page_one_extra) == end - start + 1:
        smiles_page = smiles_page_one_extra[:-1]
    # otherwise there are no more elements in the database and you need to display everything
    else:
        smiles_page = smiles_page_one_extra

    list_smiles = [dict(id=doc.reference.id, user_id=doc.get('user_id')) for doc in smiles_page]
    _ = [
        all_smiles_view['blocks'].append(
            SectionBlock(
                block_id=f'{smile["id"]}_block',
                text=MarkdownTextObject(text=f':{smile["id"]}: этот у <@{smile["user_id"]}>'),
                accessory=ButtonElement(
                    action_id='delete_smile_action',
                    text='Удалить смайлик',
                    value=smile["id"],
                    confirm=ConfirmObject(title='Удаление смайлика',
                                          text=MarkdownTextObject(
                                              text=f'Вы действительно хотите удалить смайлик <@{smile["user_id"]}>?'),
                                          confirm='Да', deny='Отмена')
                ) if admin else None
            ).to_dict()
        )
        for smile in list_smiles
    ]

    navigation_block = ActionsBlock(block_id='navigation_block', elements=[])
    metadata = dict(start_at=start)

    if start != 0:
        navigation_block.elements.append(ButtonElement(action_id='all_smiles_prev_page_action', text='Предыдущая страница'))

    if len(smiles_page_one_extra) == end - start + 1:
        metadata['end_at'] = end
        navigation_block.elements.append(ButtonElement(action_id='all_smiles_next_page_action', text='Следующая страница'))

    if navigation_block.elements:
        all_smiles_view['blocks'].append(navigation_block.to_dict())
        all_smiles_view['private_metadata'] = json.dumps(metadata)

    if add_info:
        bot.views_open(trigger_id=add_info['trigger_id'], view=all_smiles_view)
    else:
        bot.views_update(view=all_smiles_view, view_id=update_info['view_id'], hash=update_info['hash'])
