from wtforms import Form, StringField, TextAreaField, PasswordField, validators

class FileForm(Form):
    fileName = StringField('File Name', [validators.Length(min=1, max=50)])
    fileDescription = TextAreaField('File Description', [validators.Length(min=30)])
