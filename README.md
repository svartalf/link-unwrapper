# Tornado server for short links unwrapping

CPython + PyPy compatible.

## Installation

1. Clone repository
2. Install additional packages: `pip install -r requirements.txt`


## Usage

Run it: `python link_unwrapper/server.py`
Open browser: `http://127.0.0.1:8080/?url=http://t.co/3Y8k5Chaxr`
Server will respond with a link after all of the redirects: `http://pit.dirty.ru/lepro/2/2014/01/10/63597-100902-28f28836f563daf796e6966dde90522c.jpg`