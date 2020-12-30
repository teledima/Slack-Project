from flask import Blueprint, request, redirect
from slack_sdk.oauth.authorize_url_generator import AuthorizeUrlGenerator
from slack_sdk.oauth.redirect_uri_page_renderer import RedirectUriPageRenderer
from slack_sdk.web.client import WebClient
from slack_core import constants
from firebase_admin import firestore
from authorization.document_types import AuthedUser

auth_blueprint = Blueprint(name='auth', import_name=__name__, static_folder='templates')


@auth_blueprint.route('/auth', methods=['GET'])
def auth():
    code = request.args.get('code')
    if not code:
        return redirect(location=AuthorizeUrlGenerator(client_id=constants.SLACK_CLIENT_ID,
                                                       user_scopes=['chat:write']).generate(state=''),
                        code=302)
    else:
        finish_page = RedirectUriPageRenderer(install_path='/auth', redirect_uri_path='')
        response = WebClient().oauth_v2_access(client_id=constants.SLACK_CLIENT_ID,
                                               client_secret=constants.SLACK_CLIENT_SECRET,
                                               code=code)
        if response['ok']:
            db = firestore.client().collection('authed_users')
            db.document(response['authed_user']['id']).set(AuthedUser.from_dict(response))
            WebClient(constants.SLACK_OAUTH_TOKEN_BOT).chat_postMessage(text='Вы успешно авторизовались! '
                                                                             'Теперь можно пользоваться проверкой.',
                                                                        channel=response['authed_user']['id'])
            return finish_page.render_success_page(app_id=response['app_id'], team_id=response['team']['id'])
        else:
            return finish_page.render_failure_page(reason=response['error'])
