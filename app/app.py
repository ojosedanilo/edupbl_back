from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .schemas import Message

app = FastAPI(title='EduPBL')


@app.get('/', response_model=Message)
def home():
    return {'message': 'Olá, Mundo!'}


@app.get('/html', response_class=HTMLResponse)
def html():
    return """
    <html>
        <head>
            <title>Olá, Mundo!</title>
        </head>
        <body>
            <h1>Olá, Mundo!</h1>
        </body>
    </html>"""
