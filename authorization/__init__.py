from flask import Blueprint, request, render_template


auth_blueprint = Blueprint(name='auth', import_name=__name__, static_folder='templates')


@auth_blueprint.route('/auth', methods=['GET'])
def auth():
    code = request.args.get('code')
    if not code:
        return render_template('sign_in.html')
    else:
        return 'Success!'
