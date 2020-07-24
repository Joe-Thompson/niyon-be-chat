from flask import Flask, request, jsonify, render_template
from time import localtime, strftime
import settings
from flask_cors import CORS, cross_origin
from flask_socketio import SocketIO, send, join_room, leave_room, emit
from engineio.payload import Payload
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import database_calls
import os
import rooms

server = Flask(__name__)
CORS(server)
cors = CORS(server, resources={
    r"/*": {
        "origins": "*"
    }
})
Base = declarative_base()

server.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
server.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')
server.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
engine = create_engine(os.getenv('DATABASE_URI'))
Session = sessionmaker(bind=engine)
session = Session()
db = SQLAlchemy(server)
Payload.max_decode_packets = 100000
socketio = SocketIO(server, cors_allowed_origins="*")
# server.debug = True
# server.host = 'localhost'

user = []


@server.after_request
def after_request(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = 'http://localhost:3000/'
    return response


@socketio.on('join')
def on_join(data):
    new_user = None
    for id in database_calls.my_list_of_users:
        if id['user_id'] == data['id']:
            new_user = id
            break
    new_user.update({'session_id': request.sid})
    user.append(new_user)
    room = None
    for id in rooms.room_list:
        if id['id'] == data['room_id']:
            room = id['room']
    on_history(room)
    join_room(room)


def on_history(room):
    msgs = []
    current_room_msgs = []
    current_room = room
    history_messages = session.query(Messages).all()
    for message_history in history_messages:
        temp_dict = {'userid': message_history.userid,
                     'roomname': message_history.roomname,
                     'firstname': message_history.firstname,
                     'lastname': message_history.lastname,
                     'mytimestamp': message_history.mytimestamp,
                     'usertype': message_history.usertype,
                     'msg': message_history.msg}
        msgs.append(temp_dict)
    for roomname in msgs:
        if roomname['roomname'] == room:
            current_room_msgs.append(roomname)


@socketio.on('message')
def on_message(msg):
    res = None
    for sub in user:
        if sub['session_id'] == request.sid:
            res = sub
            break
    current_room = None
    for name in rooms.room_list:
        if name['room'] == msg['room']:
            current_room = name['room']
    res['msg'] = msg['msg']
    res['room_name'] = current_room
    res['timestamp'] = strftime('%b %d, %I:%M%p', localtime())
    data = Messages(
        userid=res['user_id'],
        roomname=res['room_name'],
        mytimestamp=res['timestamp'],
        usertype=res['user_type'],
        firstname=res['first_name'],
        lastname=res['last_name'],
        msg=res['msg'])
    session.add(data)
    session.commit()
    send(res, broadcast=True, room=current_room)


@server.route('/chathistory', methods=['GET'])
def get_chat_history():
    print(request)
    current_room = request.args['room_name']
    msgs = []
    current_room_msgs = []
    history_messages = session.query(Messages).all()
    for message_history in history_messages:
        temp_dict = {'first_name': message_history.firstname,
                     'last_name': message_history.lastname,
                     'user_type': message_history.usertype,
                     'msg': message_history.msg,
                     'user_id': message_history.userid,
                     'room_name': message_history.roomname,
                     'timestamp': message_history.mytimestamp,
                     }
        msgs.append(temp_dict)
    for room in msgs:
        print(room)
        if room['room_name'] == current_room:
            current_room_msgs.append(room)
    print(current_room_msgs)
    if len(current_room_msgs) < 1:
        current_room_msgs.append(
            {'first_name': 'Niyon',
             'last_name': 'Bot',
             'user_type': 'Admin',
             'msg': 'Welcome to the Niyon Chat App',
             'user_id': 0,
             'room_name': 'Any',
             'timestamp': 'Now', }
        )
    return jsonify(current_room_msgs)


class Messages(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    userid = Column(Integer)
    roomname = Column(Text)
    mytimestamp = Column(Text)
    usertype = Column(Text)
    firstname = Column(Text)
    lastname = Column(Text)
    msg = Column(Text)

    def __repr__(self):
        return "<Messages(userid='%s', roomname='%s', mytimestamp='%s', usertype='%s', firstname='%s', lastname='%s', msg='%s'>" % (
            self.userid, self.roomname, self.mytimestamp, self.usertype, self.firstname, self.lastname, self.msg)


if __name__ == '__main__':
    server.run()
