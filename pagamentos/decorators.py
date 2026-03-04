from django.shortcuts import redirect
from functools import wraps

def check_assinatura(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 1. Verifica se o usuário tem perfil e empresa
        perfil = getattr(request.user, 'perfil', None)
        empresa = perfil.empresa if perfil else None

        # 2. Se não houver empresa vinculada, manda configurar
        if not empresa:
            return redirect('configurar_empresa')

        # 3. Se houver empresa, verifica se o pagamento está ok
        if not empresa.em_dia():
            return redirect('central_assinatura') 

        return view_func(request, *args, **kwargs)
    return _wrapped_view