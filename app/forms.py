from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired

from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, DecimalRangeField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, NumberRange

from app.models import User

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')

class SlackAuthDataForm(FlaskForm):
    slack_app_token = StringField('Slack App Token', validators=[DataRequired()])
    slack_signing_secret = PasswordField('Slack Signing Secret', validators=[DataRequired()])
    submit = SubmitField('Submit')


class GmailAuthDataForm(FlaskForm):
    file = FileField('Credentials File', validators=[FileRequired()])

    submit = SubmitField('Submit')

class DevModeForm(FlaskForm):
    # app.app_context().push()
    # setting = Setting.query.filter_by(user_id=current_user.id).first()
    pscore_choices = ['raw_llm', 'bayes', 'bayes_meta']
    pscore_method = SelectField('Score Method', choices = pscore_choices, validators = [DataRequired()])
    embedding_choices = ['openai_ada_v2', 'local_bart']
    embedding_method = SelectField('Embedding Method', choices = embedding_choices, validators = [DataRequired()])
    num_neighbors = DecimalRangeField('Number NNeighbors', validators=[DataRequired(), NumberRange(min=1, max=10)])
        #,  default=setting.num_neighbors)
    num_gmail_msg = DecimalRangeField('Last N emails', validators=[DataRequired(), NumberRange(min=1, max=50)])
        #,  default=setting.num_gmail_msg)
    num_days_slack = DecimalRangeField('Last N days slack', validators=[DataRequired(), NumberRange(min=1, max=7)])
        #, default=setting.num_days_slack)
    submit = SubmitField('Submit')
