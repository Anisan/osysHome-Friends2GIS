from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired

# Определение класса формы
class SettingsForm(FlaskForm):
    token = StringField('Token', validators=[DataRequired()])
    submit = SubmitField('Submit')
