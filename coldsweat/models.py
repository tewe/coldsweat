# -*- coding: utf-8 -*-
"""
Description: database models

Copyright (c) 2013— Andrea Peltrin
Portions are copyright (c) 2013 Rui Carmo
License: MIT (see LICENSE.md for details)
"""

from os import path
from datetime import datetime
from calendar import timegm
from peewee import *

from utilities import *
import favicon
from coldsweat import config, installation_dir

# Defer database init, see connect() below
engine = config.get('database', 'engine', 'sqlite')
if engine == 'sqlite':
    from sqlite3 import IntegrityError
    coldsweat_db = SqliteDatabase(None) 
elif engine == 'mysql':
    from MySQLdb import IntegrityError
    coldsweat_db = MySQLDatabase(None)
else:
    raise ValueError('Unknown database engine %s. Should be sqlite or mysql' % engine)




class CustomModel(Model):
    """
    Binds the database to all our models
    """

    class Meta:
        database = coldsweat_db


class User(CustomModel):
    """
    Users - need at least one to store the api_key
    """
    
    DEFAULT_CREDENTIALS = 'default', 'default'

    username            = CharField(unique=True)
    password            = CharField() #@@TODO: hashed & salted
    
    email               = CharField(null=True)
    api_key             = CharField(unique=True)

    is_enabled          = BooleanField(default=True) 


    class Meta:
        db_table = 'users'
    

class Icon(CustomModel):
    """
    Feed (fav)icons, stored as data URIs
    """
    data                = CharField() 

    class Meta:
        db_table = 'icons'


class Group(CustomModel):
    """
    Feed group/folder
    """
    title               = CharField(null=True)
    
    class Meta:
        db_table = 'groups'    

class Feed(CustomModel):
    """
    Atom/RSS feed
    """
    
    # Fetch?
    is_enabled          = BooleanField(default=True) 
    
    # A URL to a small icon representing the feed
    icon                = ForeignKeyField(Icon, default=1)
    title               = CharField(default='Untitled')    
    
    # The URL of the HTML page associated with the feed
    alternate_link      = CharField(null=True)            
    
    # The URL of the feed itself (rel=self)
    self_link           = CharField()
    
    etag                = CharField(null=True)    
    last_updated_on     = DateTimeField(null=True) # As UTC
    last_checked_on     = DateTimeField(null=True) # As UTC 

    last_status         = IntegerField(null=True) # Last HTTP code
    
    error_count         = IntegerField(default=0)


    class Meta:
        indexes = (
            (('self_link',), True),
            (('last_checked_on',), False),
            #(('last_updated_on',), False),
        )
        order_by = ('-last_updated_on',)
        db_table = 'feeds'

    @property
    def last_updated_on_as_epoch(self):
        if self.last_updated_on: # Never updated?
            return datetime_as_epoch(self.last_updated_on)
        return 0 



class Entry(CustomModel):
    """
    Atom/RSS entry
    """

    # It's called 'id' in Atom parlance
    guid            = CharField() 
    
    feed            = ForeignKeyField(Feed,related_name='entries')
    
    title           = CharField(default='Untitled')
    author          = CharField(null=True)
    content         = TextField(null=True)
    
    link            = CharField()
    
    last_updated_on = DateTimeField() # As UTC

    class Meta:
        indexes = (
            #(('last_updated_on',), False),
            (('guid',), False),
            (('link',), False),
        )
        order_by = ('-last_updated_on',)
        db_table = 'entries'

    @property
    def last_updated_on_as_epoch(self):
        return datetime_as_epoch(self.last_updated_on)

    @property
    def excerpt(self):
        return get_excerpt(self.content)
                
class Saved(CustomModel):
    """
    Many-to-many relationship between Users and entries
    """
    user           = ForeignKeyField(User)
    entry          = ForeignKeyField(Entry)    
    saved_on       = DateTimeField(default=datetime.utcnow)  

    class Meta:
        indexes = (
            (('user', 'entry'), True),
        )

class Read(CustomModel):
    """
    Many-to-many relationship between Users and entries
    """
    user           = ForeignKeyField(User)
    entry          = ForeignKeyField(Entry)    
    read_on        = DateTimeField(default=datetime.utcnow) 

    class Meta:
        indexes = (
            (('user', 'entry'), True),
        )

class Subscription(CustomModel):
    """
    A user's feed subscriptions
    """
    user           = ForeignKeyField(User)
    group          = ForeignKeyField(Group)
    feed           = ForeignKeyField(Feed)

    class Meta:
        db_table = 'subscriptions'


def connect():
    """
    Shortcut to init and connect to database
    """
    
    if engine == 'sqlite':
        filename = path.join(installation_dir, config.get('database', 'filename'))
        
        coldsweat_db.init(filename)    
        
        # See http://www.sqlite.org/wal.html
        #coldsweat_db.execute_sql('PRAGMA journal_mode=WAL')
        
    elif engine == 'mysql':            
        database = config.get('database', 'database', 'coldsweat')

        kwargs = dict(
            host    = config.get('database', 'hostname', 'localhost'),
            user    = config.get('database', 'username', 'root'),
            passwd  = config.get('database', 'password', 'secret')        
        )

        coldsweat_db.init(database, **kwargs)
    
    coldsweat_db.connect()


def setup(skip_if_existing=False):
    """
    Create database and tables for all models and setup bootstrap data
    """

    connect()
    
    models = User, Icon, Feed, Entry, Group, Read, Saved, Subscription

    for model in models:
        model.create_table(skip_if_existing)

    username, password = User.DEFAULT_CREDENTIALS

    # Create the bare minimum to boostrap system
    with coldsweat_db.transaction():
        User.create(username=username, password=password, api_key=make_md5_hash('%s:%s' % (username, password)))
        Group.create(title='All entries')        
        Icon.create(data=favicon.DEFAULT_FAVICON) 
