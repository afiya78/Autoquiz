from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Quiz Bot is Alive on Heroku (quizbotafi version)!"