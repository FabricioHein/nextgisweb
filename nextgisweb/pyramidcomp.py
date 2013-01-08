# -*- coding: utf-8 -*-
import sys
from hashlib import md5
from StringIO import StringIO

from .component import Component

from pyramid.config import Configurator
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

import pyramid_tm


@Component.registry.register
class PyramidComponent(Component):
    identity = 'pyramid'

    def make_app(self, settings=None):
        settings = dict(self._settings, **settings)

        settings['mako.directories'] = 'nextgisweb:templates/'

        config = Configurator(settings=settings)

        # возможность доступа к Env через request.env
        config.set_request_property(lambda (req): self._env, 'env')

        config.include(pyramid_tm)

        assert 'secret' in settings, 'Secret not set!'
        authn_policy = AuthTktAuthenticationPolicy(secret=settings['secret'])
        config.set_authentication_policy(authn_policy)

        authz_policy = ACLAuthorizationPolicy()
        config.set_authorization_policy(authz_policy)

        config.add_route('home', '/')

        # Чтобы не приходилось вручную чистить кеш статики, сделаем
        # так, чтобы у них всегда были разные URL. В качестве ключа
        # используем хеш md5 от всех установленных в окружении пакетов,
        # который можно вытянуть через pip freeze. Так же pip freeze
        # вместе с версиями возвращает текущий коммит, для пакетов из
        # VCS, что тоже полезно.

        # Наверное это можно как-то получше сделать, но делаем так:
        # перенаправляем sys.stdout в StringIO, запускаем pip freeze и
        # затем возвращаем sys.stdout на место.

        stdout = sys.stdout
        static_key = ''

        try:
            import pip
            buf = StringIO()
            sys.stdout = buf
            pip.main(['freeze', ])
            h = md5()
            h.update(buf.getvalue())
            static_key = '/' + h.hexdigest()

        finally:
            sys.stdout = stdout

        config.add_static_view('static%s/asset' % static_key, 'static', cache_max_age=3600)
        config.add_route('amd_package', 'static%s/amd/*subpath' % static_key)

        for comp in self._env.chain('setup_pyramid'):
            comp.setup_pyramid(config)

        # TODO: не лезть в приватные переменные _env
        for comp in self._env._components.itervalues():
            # comp.setup_pyramid(config)
            comp.__class__.setup_routes(config)

        config.scan()

        return config

    settings_info = (
        dict(key='secret', desc=u"Ключ, используемый для шифрования cookies"),
    )