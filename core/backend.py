"""
Backend de autenticação LDAP customizado.

Fluxo:
  1. Recebe username + password da tela de login
  2. Verifica se existe um UsuarioCustomizado local com esse username
  3. Se existir, delega a autenticação para o LDAPBackend (django-auth-ldap)
  4. Se não existir, retorna None (usuário não cadastrado no sistema)

Isso garante que apenas militares/usuários previamente cadastrados
consigam autenticar via LDAP — não cria contas automaticamente.

Para habilitar: instale django-auth-ldap e descomente as configurações
em core/settings.py (seção LDAP).
"""

from django.contrib.auth import get_user_model


def _ldap_available():
    try:
        from django_auth_ldap.backend import LDAPBackend  # noqa: F401
        return True
    except ImportError:
        return False


class CustomLDAPBackend:
    """
    Wrapper sobre LDAPBackend que exige que o usuário já exista localmente.

    Usado em AUTHENTICATION_BACKENDS junto com ModelBackend:
        AUTHENTICATION_BACKENDS = [
            'core.backend.CustomLDAPBackend',
            'django.contrib.auth.backends.ModelBackend',
        ]
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not _ldap_available():
            return None

        from django_auth_ldap.backend import LDAPBackend

        UserModel = get_user_model()

        # Pré-requisito: o usuário deve existir no banco local
        try:
            UserModel.objects.get(username=username)
        except UserModel.DoesNotExist:
            return None

        # Autenticação via LDAP
        backend = LDAPBackend()
        return backend.authenticate(request, username=username, password=password, **kwargs)

    def get_user(self, user_id):
        if not _ldap_available():
            return None

        from django_auth_ldap.backend import LDAPBackend
        return LDAPBackend().get_user(user_id)
