from flask import Flask

app = Flask(__name__)

@app.before_first_request
def before_first():
    print("before_first_request works!")

@app.route('/')
def home():
    return "Hello from test!"

if __name__ == '__main__':
    app.run(debug=True)
