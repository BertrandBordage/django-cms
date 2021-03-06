# -*- coding: utf-8 -*-
from __future__ import with_statement
from contextlib import contextmanager
import inspect
from cms.models.titlemodels import Title
from cms.utils import get_language_from_request
from cms.utils.compat import DJANGO_1_6
from cms.utils.i18n import force_language, hide_untranslated
from django.conf import settings
from django.core.urlresolvers import NoReverseMatch, reverse, resolve
from django.utils import six


def set_language_changer(request, func):
    """
    
    Sets a language chooser function that accepts one parameter: language
    The function should return a url in the supplied language
    normally you would want to give it the get_absolute_url function with an optional language parameter
    example:
    
    def get_absolute_url(self, language=None):
        reverse('product_view', args=[self.get_slug(language=language)])
        
    Use this function in your nav extender views that have i18n slugs.
    """
    request._language_changer = func


def language_changer_decorator(language_changer):
    """
    A decorator wrapper for set_language_changer.
    
        from menus.utils import language_changer_decorator
        
        @language_changer_decorator(function_get_language_changer_url)
        def my_view_function(request, somearg):
            pass
    """
    def _decorator(func):
        def _wrapped(request, *args, **kwargs):
            set_language_changer(request, language_changer)
            return func(request, *args, **kwargs)
        _wrapped.__name__ = func.__name__
        _wrapped.__doc__ = func.__doc__
        return _wrapped
    return _decorator


class DefaultLanguageChanger(object):
    def __init__(self, request):
        self.request = request
        self._app_path = None

    @property
    def app_path(self):
        if self._app_path is None:
            self._app_path = self.request.path_info

            language_code = (get_language_from_request(self.request)
                             if settings.USE_I18N else settings.LANGUAGE_CODE)
            page_path = self.get_page_path(language_code)
            if page_path:
                self._app_path = self.app_path[len(page_path):]
        return self._app_path

    def get_page_path(self, lang):
        page = getattr(self.request, 'current_page', None)
        if page is not None:
            with force_language(lang):
                try:
                    return page.get_absolute_url(language=lang, fallback=False)
                except (Title.DoesNotExist, NoReverseMatch):
                    if hide_untranslated(lang) and settings.USE_I18N:
                        return '/%s/' % lang
                    return page.get_absolute_url(language=lang, fallback=True)
        if settings.USE_I18N:
            return '/%s/' % lang
        return "/"

    def __call__(self, lang):
        page_language = get_language_from_request(self.request)
        with force_language(page_language):
            try:
                view = resolve(self.request.path_info)
            except:
                view = None
        if hasattr(self.request, 'toolbar') and self.request.toolbar.obj:
            with force_language(lang):
                try:
                    return self.request.toolbar.obj.get_absolute_url()
                except:
                    pass
        elif view and view.url_name not in ('pages-details-by-slug', 'pages-root'):
            view_name = view.url_name
            if view.namespace:
                view_name = "%s:%s" % (view.namespace, view_name)
            with force_language(lang):
                with static_stringifier(view):  # This is a fix for Django < 1.7
                    try:
                        return reverse(view_name, args=view.args, kwargs=view.kwargs, current_app=view.app_name)
                    except NoReverseMatch:
                        pass
        return '%s%s' % (self.get_page_path(lang), self.app_path)


@contextmanager
def static_stringifier(view):
    """
    In Django < 1.7 reverse tries to convert to string the arguments without
    checking whether they are classes or instances.

    This context manager monkeypatches the __unicode__ method of each view
    argument if it's a class definition to render it a static method.
    Before leaving we undo the monkeypatching.
    """
    if DJANGO_1_6:
        for idx, arg in enumerate(view.args):
            if inspect.isclass(arg):
                if hasattr(arg, '__unicode__'):
                    @staticmethod
                    def custom_str():
                        return six.text_type(arg)
                    arg._original = arg.__unicode__
                    arg.__unicode__ = custom_str
                view.args[idx] = arg
        for key, arg in view.kwargs.items():
            if inspect.isclass(arg):
                if hasattr(arg, '__unicode__'):
                    @staticmethod
                    def custom_str():
                        return six.text_type(arg)
                    arg._original = arg.__unicode__
                    arg.__unicode__ = custom_str
                view.kwargs[key] = arg
    yield
    if DJANGO_1_6:
        for idx, arg in enumerate(view.args):
            if inspect.isclass(arg):
                if hasattr(arg, '__unicode__'):
                    arg.__unicode__ = arg._original
        for key, arg in view.kwargs.items():
            if inspect.isclass(arg):
                if hasattr(arg, '__unicode__'):
                    arg.__unicode__ = arg._original