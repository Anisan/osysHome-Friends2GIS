from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired

# Определение класса формы
class SettingsForm(FlaskForm):
    token = StringField('Token', validators=[DataRequired()])
    min_update_interval = IntegerField('Min update interval (sec)', validators=[DataRequired()])
    submit = SubmitField('Submit')
