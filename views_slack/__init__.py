from flask import Blueprint
from slack_core import SlackInteractionsAdapter

from .app_home import (
    open_update_smile_view,
    update_smile_user_select,
    open_all_smiles,
    all_smiles_next_page,
    all_smiles_prev_page,
    delete_smile,
    submit_update_smile
)
from .check_shortcut import (
    open_check_form,
    input_link,
    submit_check_form
)


views_endpoint_blueprint = Blueprint('views_endpoint', __name__)
interactions_adapter = SlackInteractionsAdapter(router=views_endpoint_blueprint, rule='/views-endpoint')

interactions_adapter.on('shortcut.check_form_callback', open_check_form)
interactions_adapter.on('block_actions.input_link_action', input_link)
interactions_adapter.on('view_submission.check_form_callback', submit_check_form)

interactions_adapter.on('block_actions.open_update_smile_view_action', open_update_smile_view)
interactions_adapter.on('block_actions.user_select_action', update_smile_user_select)
interactions_adapter.on('block_actions.open_all_smiles_action', open_all_smiles)
interactions_adapter.on('block_actions.all_smiles_next_page_action', all_smiles_next_page)
interactions_adapter.on('block_actions.all_smiles_prev_page_action', all_smiles_prev_page)
interactions_adapter.on('block_actions.delete_smile_action', delete_smile)
interactions_adapter.on('view_submission.update_smile_callback', submit_update_smile)
