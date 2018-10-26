from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from wtforms.fields.html5 import EmailField

class ContactForm(Form):
    firstName = StringField('First Name', [validators.Length(min=1, max=50)])
    lastName = StringField('Last Name', [validators.Length(min=1, max=50)])
    email = EmailField('Email address', [validators.DataRequired(), validators.Email()])
    emailSubject = StringField('Email Subject', [validators.Length(min=1, max=50)])
    emailContent = StringField('Your message...', [validators.Length(min=1, max=50)])
