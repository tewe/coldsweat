# -*- coding: utf-8 -*-
"""
Description: Cascades through several applications, 
  so long as applications return '404 Not Found'

Copyright (c) 2013— Andrea Peltrin
Portions are copyright (c) 2005 Ian Bicking and contributors
License: MIT (see LICENSE.md for details)
"""
import tempfile
from cStringIO import StringIO

from webob.exc import HTTPException, HTTPNotFound
from coldsweat import log
    
class Cascade(object):

    """
    Passed a list of applications, ``Cascade`` will try each of them
    in turn.  If one returns a status code listed in ``catch`` (by
    default just ``404 Not Found``) then the next application is
    tried.

    If all applications fail, then the last application's failure
    response is used.

    Instances of this class are WSGI applications.
    """

    def __init__(self, applications, catch=(HTTPNotFound,)):
        self.apps = applications
        self.catch_codes = {}
        self.catch_exceptions = []
        for error in catch:
            if issubclass(error, HTTPException):
                exc = error
                code = error.code
            else:
                raise ValueError('%s must be a subclass of webob.exc.HTTPException' % error)
            self.catch_codes[code] = exc
            self.catch_exceptions.append(exc)
        self.catch_exceptions = tuple(self.catch_exceptions)
                
    def __call__(self, environ, start_response):
        """
        WSGI application interface
        """
        failed = []
        def repl_start_response(status, headers, exc_info=None):
            code = int(status.split(None, 1)[0])
            if code in self.catch_codes:
                failed.append(None)
                return _consuming_writer
            return start_response(status, headers, exc_info)

        try:
            length = int(environ.get('CONTENT_LENGTH', 0) or 0)
        except ValueError:
            length = 0
        #log.debug('Lenght is %d bytes' % length)
        if length > 0:
            # We have to copy wsgi.input
            copy_wsgi_input = True
            if length > 4096 or length < 0:
                f = tempfile.TemporaryFile()
                if length < 0:
                    f.write(environ['wsgi.input'].read())
                else:
                    copy_length = length
                    while copy_length > 0:
                        chunk = environ['wsgi.input'].read(min(copy_length, 4096))
                        if not chunk:
                            raise IOError("Request body truncated")
                        f.write(chunk)
                        copy_length -= len(chunk)
                f.seek(0)
            else:
                f = StringIO(environ['wsgi.input'].read(length))
            environ['wsgi.input'] = f
        else:
            copy_wsgi_input = False
        for app in self.apps[:-1]:
            environ_copy = environ.copy()
            if copy_wsgi_input:
                environ_copy['wsgi.input'].seek(0)
            failed = []
            try:
                v = app(environ_copy, repl_start_response)
                if not failed:
                    return v
                else:
                    if hasattr(v, 'close'):
                        # Exhaust the iterator first:
                        list(v)
                        # then close:
                        v.close()
            except self.catch_exceptions, exc:
                pass
        if copy_wsgi_input:
            environ['wsgi.input'].seek(0)
        return self.apps[-1](environ, start_response)

def _consuming_writer(s):
    pass
